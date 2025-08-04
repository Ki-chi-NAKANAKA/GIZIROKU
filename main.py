import sys
import os
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QSplitter,
    QListWidget,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QFileDialog,
    QTabWidget,
    QTextEdit,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QObject, QStandardPaths
from pathlib import Path

# Import processors and prompts
from src.processors.openai_api import OpenAIApiProcessor
from src.processors.ollama_processor import OllamaProcessor
from src.prompts import SUMMARY_PROMPT, DECISIONS_PROMPT, TODO_PROMPT
from src.data_manager import DataManager

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

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

class MinutesViewWidget(QWidget):
    # Signals to request export, format as argument
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
        export_as_md.triggered.connect(lambda: self.export_requested.emit("markdown"))

        export_as_txt = QAction("テキストとして保存 (.txt)", self)
        export_as_txt.triggered.connect(lambda: self.export_requested.emit("text"))

        export_menu.addAction(export_as_md)
        export_menu.addAction(export_as_txt)

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

        # --- Setup Data Management ---
        app_data_path = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
        self.data_manager = DataManager(base_dir=app_data_path)
        try:
            self.data_manager.initialize_database()
        except Exception as e:
            QMessageBox.critical(self, "データベースエラー", f"データベースの初期化に失敗しました: {e}")
            sys.exit(1)

        self.api_key = os.getenv("OPENAI_API_KEY")
        self.ollama_host = "http://localhost:11434"
        self.ollama_model = "llama3"
        main_widget = QWidget()
        self.main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)
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

        # --- Member Variables ---
        self.transcription_thread = None
        self.llm_thread = None
        self.minutes_view = None
        self.current_filepath = None

    def setup_file_drop_view(self):
        if self.splitter.widget(1):
            self.splitter.widget(1).setParent(None)
        file_drop_widget = FileDropWidget()
        file_drop_widget.file_dropped.connect(self.handle_file_selected)
        file_drop_widget.select_file_button.clicked.connect(self.open_file_dialog)
        self.splitter.addWidget(file_drop_widget)

    @Slot()
    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "音声ファイルを選択", "", "音声ファイル (*.mp3 *.wav *.m4a);;全てのファイル (*)")
        if file_path:
            self.handle_file_selected(file_path)

    def populate_minutes_list(self):
        self.minutes_list.blockSignals(True)
        self.minutes_list.clear()
        records = self.data_manager.load_all_minutes()
        for record_id, title, created_at in records:
            # Format timestamp for display
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
            QMessageBox.warning(self, "エラー", f"ID {minute_id} の議事録詳細を読み込めませんでした。")
            return

        # Switch to the minutes view if not already visible
        if not isinstance(self.splitter.widget(1), MinutesViewWidget):
            self.minutes_view = MinutesViewWidget()
            self.minutes_view.export_requested.connect(self.on_export_requested)
            self.splitter.widget(1).setParent(None)
            self.splitter.addWidget(self.minutes_view)

        # Populate the tabs
        self.minutes_view.set_text_for_task("summary", details.get("summary", ""))
        self.minutes_view.set_text_for_task("decisions", details.get("decisions", ""))
        self.minutes_view.set_text_for_task("todo", details.get("todo", ""))
        self.minutes_view.set_text_for_task("full_text", details.get("full_text", ""))


    @Slot(str)
    def handle_file_selected(self, file_path):
        if not self.api_key:
            QMessageBox.critical(self, "APIキー未設定", "環境変数 `OPENAI_API_KEY` が設定されていません。")
            return

        self.current_filepath = file_path
        file_name = Path(file_path).name

        # Temporarily disable selection signals while processing
        self.minutes_list.blockSignals(True)

        list_item = QListWidgetItem(f"処理中... - {file_name}")
        list_item.setData(Qt.UserRole, None) # No ID yet
        self.minutes_list.insertItem(0, list_item)
        self.minutes_list.setCurrentItem(list_item)

        self.minutes_view = MinutesViewWidget()
        self.minutes_view.export_requested.connect(self.on_export_requested) # Connect signal
        self.splitter.widget(1).setParent(None)
        self.splitter.addWidget(self.minutes_view)
        self.minutes_view.show_processing_status(f"「{file_name}」を処理中...\n\nAPIに接続して文字起こしをしています。")
        self.start_transcription_thread(file_path)

    def start_transcription_thread(self, file_path):
        self.transcription_thread = QThread()
        worker = TranscriptionWorker(OpenAIApiProcessor(api_key=self.api_key), file_path)
        worker.moveToThread(self.transcription_thread)
        self.transcription_thread.started.connect(worker.run)
        worker.signals.finished.connect(self.on_transcription_finished)
        worker.signals.error.connect(self.on_transcription_error)
        worker.signals.finished.connect(self.transcription_thread.quit)
        worker.signals.error.connect(self.transcription_thread.quit)
        self.transcription_thread.finished.connect(self.transcription_thread.deleteLater)
        self.transcription_thread.start()

    @Slot(str)
    def on_transcription_finished(self, text):
        self.minutes_view.set_text_for_task("full_text", text)
        self.minutes_view.show_processing_status("LLMで要約などを生成中...", "summary")
        self.start_llm_thread(text)

    @Slot(str)
    def on_transcription_error(self, error_message):
        self.minutes_view.show_processing_status(f"文字起こしエラー:\n\n{error_message}")

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
        # Stop the thread once the worker is done (all tasks completed)
        # A bit of a simplification; a more robust approach might use a task counter
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
        if self.llm_task_count >= 3: # summary, decisions, todo
            self.llm_thread.quit()

            try:
                all_texts = self.minutes_view.get_all_texts()
                new_id = self.data_manager.save_minutes(self.current_filepath, all_texts)

                current_item = self.minutes_list.currentItem()
                if current_item:
                    current_item.setData(Qt.UserRole, new_id)
                    # Update text now that we have the final info
                    created_at = datetime.now().strftime('%Y-%m-%d %H:%M')
                    title = Path(self.current_filepath).name
                    current_item.setText(f"{created_at}\n{title}")

                QMessageBox.information(self, "保存完了", "議事録の処理と保存が完了しました。")
                self.minutes_list.blockSignals(False)

            except Exception as e:
                QMessageBox.critical(self, "保存エラー", f"議事録の保存中にエラーが発生しました:\n{e}")
                self.minutes_list.blockSignals(False)

    @Slot(str)
    def on_llm_error(self, error_message):
        self.minutes_view.show_processing_status(f"LLMエラー:\n\n{error_message}", "summary")
        self.minutes_view.show_processing_status("", "decisions")
        self.minutes_view.show_processing_status("", "todo")
        if self.llm_thread and self.llm_thread.isRunning():
            self.llm_thread.quit()

    def _format_content(self, content: dict, file_format: str) -> str:
        """Formats the content for exporting."""
        if file_format == "markdown":
            return f"""
# 議事録

## 要約
{content['summary']}

## 決定事項
{content['decisions']}

## ToDo
{content['todo']}

---

## 全文文字起こし
{content['full_text']}
"""
        else:  # Plain text
            return f"""
議事録
====================

[要約]
{content['summary']}

--------------------

[決定事項]
{content['decisions']}

--------------------

[ToDo]
{content['todo']}

--------------------

[全文文字起こし]
{content['full_text']}
"""

    @Slot(str)
    def on_export_requested(self, file_format):
        if not self.minutes_view:
            return

        current_item = self.minutes_list.currentItem()
        if current_item:
            base_name = Path(current_item.text()).stem
        else:
            base_name = "議事録"

        if file_format == "markdown":
            suffix = ".md"
            file_filter = "Markdownファイル (*.md)"
        elif file_format == "text":
            suffix = ".txt"
            file_filter = "テキストファイル (*.txt)"
        else:
            return

        default_path = f"{base_name}{suffix}"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "名前を付けて保存", default_path, file_filter
        )

        if file_path:
            try:
                all_texts = self.minutes_view.get_all_texts()
                formatted_content = self._format_content(all_texts, file_format)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(formatted_content.strip())
                QMessageBox.information(self, "成功", f"ファイルを保存しました:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"ファイルの保存中にエラーが発生しました:\n{e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
