import sys
from datetime import datetime
from pathlib import Path

import pypandoc
from PySide6.QtCore import Qt, QObject, QStandardPaths, Signal, Slot, QThread
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Import processors and prompts
from src.data_manager import DataManager
from src.processors.ollama_processor import OllamaProcessor
from src.processors.openai_api import OpenAIApiProcessor
from src.prompts import DECISIONS_PROMPT, SUMMARY_PROMPT, TODO_PROMPT
from src.settings_dialog import SettingsDialog
from src.settings_manager import SettingsManager

# --- Workers for async processing ---
class TranscriptionWorkerSignals(QObject):
    finished = Signal(str)
    error = Signal(str)

class TranscriptionWorker(QObject):
    def __init__(self, processor, file_path):
        super().__init__()
        self.signals = TranscriptionWorkerSignals()
        self.processor = processor
        self.file_path = file_path

    @Slot()
    def run(self):
        try:
            result = self.processor.transcribe(self.file_path)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))

class LLMWorkerSignals(QObject):
    finished = Signal(str, str)  # task_type, result
    error = Signal(str)

class LLMWorker(QObject):
    def __init__(self, processor, text_to_process, model_name):
        super().__init__()
        self.signals = LLMWorkerSignals()
        self.processor = processor
        self.text_to_process = text_to_process
        self.model_name = model_name
        self.tasks = {
            "summary": SUMMARY_PROMPT,
            "decisions": DECISIONS_PROMPT,
            "todo": TODO_PROMPT,
        }

    @Slot()
    def run(self):
        try:
            for task_type, prompt in self.tasks.items():
                result = self.processor.generate(
                    model=self.model_name,
                    system_prompt=prompt,
                    user_text=self.text_to_process,
                )
                self.signals.finished.emit(task_type, result)
        except Exception as e:
            self.signals.error.emit(f"LLM処理中にエラー: {e}")

class ExportWorkerSignals(QObject):
    finished = Signal(str)
    error = Signal(str)

class ExportWorker(QObject):
    def __init__(self, content, file_path, file_format):
        super().__init__()
        self.signals = ExportWorkerSignals()
        self.content = content
        self.file_path = file_path
        self.file_format = file_format

    @Slot()
    def run(self):
        try:
            if self.file_format == "word":
                try:
                    pypandoc.convert_text(
                        self.content,
                        'docx',
                        format='md',
                        outputfile=self.file_path,
                        extra_args=['--standalone']
                    )
                except OSError as e:
                    # This often means pandoc is not installed
                    if "No such file" in str(e):
                        raise RuntimeError(
                            "pandocが見つかりません。Word形式への変換にはpandocのインストールが必要です。"
                        )
                    raise e
            else:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    f.write(self.content)
            self.signals.finished.emit(self.file_path)
        except Exception as e:
            self.signals.error.emit(str(e))

# --- UI Widgets ---
class FileDropWidget(QWidget):
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self.drop_label = QLabel("ここに音声ファイルをドラッグ＆ドロップ", self)
        self.drop_label.setAlignment(Qt.AlignCenter)
        or_label = QLabel("または", self)
        or_label.setAlignment(Qt.AlignCenter)
        self.select_file_button = QPushButton("ファイルを選択", self)
        layout.addStretch()
        layout.addWidget(self.drop_label)
        layout.addWidget(or_label)
        layout.addWidget(self.select_file_button)
        layout.addStretch()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1:
            event.acceptProposedAction()
            self.drop_label.setText("ドロップしてファイルを追加")
            self.setStyleSheet("background-color: #e0e0e0;")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.drop_label.setText("ここに音声ファイルをドラッグ＆ドロップ")
        self.setStyleSheet("")

    def dropEvent(self, event):
        self.dragLeaveEvent(event)
        file_path = event.mimeData().urls()[0].toLocalFile()
        self.file_dropped.emit(file_path)


class MinutesViewWidget(QWidget):
    export_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout = QHBoxLayout()
        self.tabs = QTabWidget()

        self.export_button = QPushButton("エクスポート▼")
        export_menu = QMenu(self)
        self.export_button.setMenu(export_menu)

        export_as_md = QAction("Markdownとして保存 (.md)", self)
        export_as_md.triggered.connect(
            lambda: self.export_requested.emit("markdown"))

        export_as_txt = QAction("テキストとして保存 (.txt)", self)
        export_as_txt.triggered.connect(
            lambda: self.export_requested.emit("text"))

        export_as_docx = QAction("Wordとして保存 (.docx)", self)
        export_as_docx.triggered.connect(
            lambda: self.export_requested.emit("word"))

        export_menu.addAction(export_as_md)
        export_menu.addAction(export_as_txt)
        export_menu.addAction(export_as_docx)

        top_bar_layout.addWidget(self.tabs)
        top_bar_layout.addWidget(self.export_button)
        layout.addLayout(top_bar_layout)
        self.summary_edit = QTextEdit()
        self.decisions_edit = QTextEdit()
        self.todo_edit = QTextEdit()
        self.full_text_edit = QTextEdit()
        self.tabs.addTab(self.summary_edit, "要約")
        self.tabs.addTab(self.decisions_edit, "決定事項")
        self.tabs.addTab(self.todo_edit, "ToDo")
        self.tabs.addTab(self.full_text_edit, "全文")

    def get_all_texts(self):
        return {
            "summary": self.summary_edit.toPlainText(),
            "decisions": self.decisions_edit.toPlainText(),
            "todo": self.todo_edit.toPlainText(),
            "full_text": self.full_text_edit.toPlainText(),
        }

    def set_text_for_task(self, task_type, text):
        if task_type == "summary":
            self.summary_edit.setPlainText(text)
        elif task_type == "decisions":
            self.decisions_edit.setPlainText(text)
        elif task_type == "todo":
            self.todo_edit.setPlainText(text)
        elif task_type == "full_text":
            self.full_text_edit.setPlainText(text)

    def show_processing_status(self, message, task_type="full_text"):
        if task_type == "full_text":
            self.full_text_edit.setPlainText(message)
            self.summary_edit.setPlainText("LLMで生成中...")
            self.decisions_edit.setPlainText("LLMで生成中...")
            self.todo_edit.setPlainText("LLMで生成中...")
        elif task_type == "summary":
            self.summary_edit.setPlainText(message)
        elif task_type == "decisions":
            self.decisions_edit.setPlainText(message)
        elif task_type == "todo":
            self.todo_edit.setPlainText(message)
        self.tabs.setCurrentWidget(self.full_text_edit)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("議事録自動生成アプリ")
        self.resize(1024, 768)

        # --- Setup Managers ---
        self.settings_manager = SettingsManager()
        app_data_path = Path(
            QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
        self.data_manager = DataManager(base_dir=app_data_path)
        try:
            self.data_manager.initialize_database()
        except Exception as e:
            QMessageBox.critical(self, "データベースエラー",
                                 f"データベースの初期化に失敗しました: {e}")
            sys.exit(1)

        self._load_settings()

        # --- UI Setup ---
        main_widget = QWidget()
        self.main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        self._create_menu_bar()
        self._create_status_bar()

        top_bar_layout = QHBoxLayout()
        self.new_button = QPushButton("[+] 新規作成")
        top_bar_layout.addWidget(self.new_button)
        top_bar_layout.addStretch()
        self.main_layout.addLayout(top_bar_layout)
        self.splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.splitter)
        self.minutes_list = QListWidget()
        self.splitter.addWidget(self.minutes_list)

        self.populate_minutes_list()

        self.setup_file_drop_view()
        self.splitter.setSizes([250, 750])

        # --- Connections ---
        self.new_button.clicked.connect(self.setup_file_drop_view)
        self.minutes_list.currentItemChanged.connect(self.on_minute_selected)
        self.minutes_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.minutes_list.customContextMenuRequested.connect(
            self.show_list_context_menu)

        # --- Member Variables ---
        self.is_processing = False
        self.transcription_thread = None
        self.llm_thread = None
        self.export_thread = None
        self.minutes_view = None
        self.current_filepath = None

    def setup_file_drop_view(self):
        if self.splitter.widget(1):
            self.splitter.widget(1).setParent(None)
        file_drop_widget = FileDropWidget()
        file_drop_widget.file_dropped.connect(self.handle_file_selected)
        file_drop_widget.select_file_button.clicked.connect(
            self.open_file_dialog)
        self.splitter.addWidget(file_drop_widget)

    @Slot()
    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "音声ファイルを選択", "",
            "音声ファイル (*.mp3 *.wav *.m4a);;全てのファイル (*)")
        if file_path:
            self.handle_file_selected(file_path)

    def populate_minutes_list(self):
        self.minutes_list.blockSignals(True)
        self.minutes_list.clear()
        records = self.data_manager.load_all_minutes()
        for record_id, title, created_at in records:
            ts = datetime.fromisoformat(created_at).strftime('%Y-%m-%d %H:%M')
            item = QListWidgetItem(f"{ts}\n{title}")
            item.setData(Qt.UserRole, record_id)
            self.minutes_list.addItem(item)
        self.minutes_list.blockSignals(False)

    @Slot(QListWidgetItem, QListWidgetItem)
    def on_minute_selected(self, current_item, previous_item):
        if not current_item:
            return

        minute_id = current_item.data(Qt.UserRole)
        if not minute_id:
            return

        details = self.data_manager.load_minute_details(minute_id)
        if not details:
            QMessageBox.warning(self, "エラー",
                                f"ID {minute_id} の議事録詳細を読み込めませんでした。")
            return

        if not isinstance(self.splitter.widget(1), MinutesViewWidget):
            self.minutes_view = MinutesViewWidget()
            self.minutes_view.export_requested.connect(
                self.on_export_requested)
            self.splitter.widget(1).setParent(None)
            self.splitter.addWidget(self.minutes_view)

        self.minutes_view.set_text_for_task(
            "summary", details.get("summary", ""))
        self.minutes_view.set_text_for_task(
            "decisions", details.get("decisions", ""))
        self.minutes_view.set_text_for_task(
            "todo", details.get("todo", ""))
        self.minutes_view.set_text_for_task(
            "full_text", details.get("full_text", ""))

    def set_ui_enabled(self, enabled):
        """Enable or disable UI elements during processing."""
        self.minutes_list.setEnabled(enabled)
        self.new_button.setEnabled(enabled)
        # We don't disable the export button as it requires a finished view anyway

    @Slot(str)
    def handle_file_selected(self, file_path):
        if self.is_processing:
            QMessageBox.warning(self, "処理中", "現在、別の処理を実行中です。完了するまでお待ちください。")
            return

        if not self.api_key:
            QMessageBox.critical(
                self, "APIキー未設定",
                "APIキーが設定されていません。メニューの「ファイル」>「設定...」から設定してください。")
            return

        self.is_processing = True
        self.set_ui_enabled(False)
        self.current_filepath = file_path
        file_name = Path(file_path).name

        self.minutes_list.blockSignals(True)

        list_item = QListWidgetItem(f"処理中... - {file_name}")
        list_item.setData(Qt.UserRole, None)  # No ID yet
        self.minutes_list.insertItem(0, list_item)
        self.minutes_list.setCurrentItem(list_item)

        self.minutes_view = MinutesViewWidget()
        self.minutes_view.export_requested.connect(self.on_export_requested)
        self.splitter.widget(1).setParent(None)
        self.splitter.addWidget(self.minutes_view)
        self.minutes_view.show_processing_status(
            f"「{file_name}」を処理中...\n\nAPIに接続して文字起こしをしています。")
        self.start_transcription_thread(file_path)

    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def start_transcription_thread(self, file_path):
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage("文字起こしを実行中...")
        self.transcription_thread = QThread()
        worker = TranscriptionWorker(
            OpenAIApiProcessor(api_key=self.api_key), file_path)
        worker.moveToThread(self.transcription_thread)
        self.transcription_thread.started.connect(worker.run)
        worker.signals.finished.connect(self.on_transcription_finished)
        worker.signals.error.connect(self.on_transcription_error)
        worker.signals.finished.connect(self.transcription_thread.quit)
        worker.signals.error.connect(self.transcription_thread.quit)
        self.transcription_thread.finished.connect(
            self.transcription_thread.deleteLater)
        self.transcription_thread.start()

    @Slot(str)
    def on_transcription_finished(self, text):
        self.status_bar.showMessage("LLMで要約などを生成中...", 5000)
        self.minutes_view.set_text_for_task("full_text", text)
        self.start_llm_thread(text)

    @Slot(str)
    def on_transcription_error(self, error_message):
        self.progress_bar.setVisible(False)
        self.status_bar.clearMessage()
        self.minutes_view.show_processing_status(
            f"文字起こしエラー:\n\n{error_message}")
        self.is_processing = False
        self.set_ui_enabled(True)

    def start_llm_thread(self, text):
        self.llm_thread = QThread()
        try:
            processor = OllamaProcessor(host=self.ollama_host)
        except Exception as e:
            self.on_llm_error(str(e))
            return
        worker = LLMWorker(processor, text, self.ollama_model)
        worker.moveToThread(self.llm_thread)
        self.llm_thread.started.connect(worker.run)
        worker.signals.finished.connect(self.on_llm_task_finished)
        worker.signals.error.connect(self.on_llm_error)
        self.llm_thread.finished.connect(worker.deleteLater)
        self.llm_thread.finished.connect(self.llm_thread.deleteLater)
        worker.signals.finished.connect(
            lambda task, result: self.check_llm_tasks_finished()
        )
        self.llm_thread.start()
        self.llm_task_count = 0

    @Slot(str, str)
    def on_llm_task_finished(self, task_type, result):
        self.minutes_view.set_text_for_task(task_type, result)
        self.llm_task_count += 1

    def check_llm_tasks_finished(self):
        if self.llm_task_count >= 3:  # summary, decisions, todo
            self.llm_thread.quit()
            self.progress_bar.setVisible(False)
            self.status_bar.showMessage("処理が完了しました。", 5000)

            try:
                all_texts = self.minutes_view.get_all_texts()
                new_id = self.data_manager.save_minutes(
                    self.current_filepath, all_texts)

                current_item = self.minutes_list.currentItem()
                if current_item:
                    current_item.setData(Qt.UserRole, new_id)
                    created_at = datetime.now().strftime('%Y-%m-%d %H:%M')
                    title = Path(self.current_filepath).name
                    current_item.setText(f"{created_at}\n{title}")

            except Exception as e:
                QMessageBox.critical(self, "保存エラー",
                                     f"議事録の保存中にエラーが発生しました:\n{e}")
            finally:
                self.is_processing = False
                self.set_ui_enabled(True)
                self.minutes_list.blockSignals(False)

    def show_list_context_menu(self, position):
        item = self.minutes_list.itemAt(position)
        if not item:
            return

        menu = QMenu()
        delete_action = QAction("この議事録を削除", self)
        delete_action.triggered.connect(self.delete_selected_minute)
        menu.addAction(delete_action)

        menu.exec(self.minutes_list.mapToGlobal(position))

    def delete_selected_minute(self):
        current_item = self.minutes_list.currentItem()
        if not current_item:
            return

        minute_id = current_item.data(Qt.UserRole)
        if not minute_id:
            QMessageBox.warning(self, "削除不可",
                                "この議事録はまだ処理中か、無効なため削除できません。")
            return

        reply = QMessageBox.question(
            self,
            "削除の確認",
            (f"「{current_item.text().splitlines()[1]}」\n\n"
             "この議事録を完全に削除しますか？\nこの操作は元に戻せません。"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.data_manager.delete_minute(minute_id)
                row = self.minutes_list.row(current_item)
                self.minutes_list.takeItem(row)
                self.setup_file_drop_view()
            except Exception as e:
                QMessageBox.critical(self, "エラー",
                                     f"削除中にエラーが発生しました:\n{e}")

    @Slot(str)
    def on_llm_error(self, error_message):
        self.progress_bar.setVisible(False)
        self.status_bar.clearMessage()
        self.minutes_view.show_processing_status(
            f"LLMエラー:\n\n{error_message}", "summary")
        self.minutes_view.show_processing_status("", "decisions")
        self.minutes_view.show_processing_status("", "todo")
        if self.llm_thread and self.llm_thread.isRunning():
            self.llm_thread.quit()
        self.is_processing = False
        self.set_ui_enabled(True)

    def _format_content(self, content: dict, file_format: str) -> str:
        """Formats the content for exporting."""
        if file_format == "markdown":
            return (
                f"# 議事録\n\n"
                f"## 要約\n{content['summary']}\n\n"
                f"## 決定事項\n{content['decisions']}\n\n"
                f"## ToDo\n{content['todo']}\n\n"
                f"---\n\n"
                f"## 全文文字起こし\n{content['full_text']}\n"
            )
        else:  # Plain text
            return (
                f"議事録\n====================\n\n"
                f"[要約]\n{content['summary']}\n\n"
                f"--------------------\n\n"
                f"[決定事項]\n{content['decisions']}\n\n"
                f"--------------------\n\n"
                f"[ToDo]\n{content['todo']}\n\n"
                f"--------------------\n\n"
                f"[全文文字起こし]\n{content['full_text']}\n"
            )

    @Slot(str)
    def on_export_requested(self, file_format):
        if not self.minutes_view:
            return

        current_item = self.minutes_list.currentItem()
        if current_item:
            base_name = Path(current_item.text().splitlines()[1]).stem
        else:
            base_name = "議事録"

        if file_format == "markdown":
            suffix = ".md"
            file_filter = "Markdownファイル (*.md)"
        elif file_format == "text":
            suffix = ".txt"
            file_filter = "テキストファイル (*.txt)"
        elif file_format == "word":
            suffix = ".docx"
            file_filter = "Wordドキュメント (*.docx)"
        else:
            return

        default_path = f"{base_name}{suffix}"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "名前を付けて保存", default_path, file_filter
        )

        if file_path:
            all_texts = self.minutes_view.get_all_texts()
            content_to_export = self._format_content(all_texts, "markdown")

            self.export_thread = QThread()
            worker = ExportWorker(content_to_export, file_path, file_format)
            worker.moveToThread(self.export_thread)

            worker.signals.finished.connect(self.on_export_finished)
            worker.signals.error.connect(self.on_export_error)

            self.export_thread.started.connect(worker.run)
            self.export_thread.finished.connect(worker.deleteLater)
            self.export_thread.finished.connect(self.export_thread.deleteLater)
            self.export_thread.start()

            self.status_bar.showMessage(
                f"{file_format}形式でエクスポート中...")
            self.progress_bar.setVisible(True)

    @Slot(str)
    def on_export_finished(self, file_path):
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage(f"ファイルを保存しました: {file_path}", 5000)
        self.export_thread.quit()

    @Slot(str)
    def on_export_error(self, error_message):
        self.progress_bar.setVisible(False)
        self.status_bar.clearMessage()
        QMessageBox.critical(self, "エラー",
                             f"エクスポート中にエラーが発生しました:\n{error_message}")
        self.export_thread.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
