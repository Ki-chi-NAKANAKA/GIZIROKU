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
from PySide6.QtCore import Qt, Signal, Slot, QThread, QObject
from pathlib import Path

# Import processors and prompts
from src.processors.openai_api import OpenAIApiProcessor
from src.processors.ollama_processor import OllamaProcessor
from src.prompts import SUMMARY_PROMPT, DECISIONS_PROMPT, TODO_PROMPT

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

class MinutesViewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout = QHBoxLayout()
        self.tabs = QTabWidget()
        self.export_button = QPushButton("エクスポート▼")
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
        self.api_key = os.getenv("OPENAI_API_KEY")
        # TODO: Make these configurable
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
        self.minutes_list.addItems(["2025-08-01 定例会", "2025-07-25 A案件...", "2025-07-18 Bプロ..."])
        self.splitter.addWidget(self.minutes_list)
        self.setup_file_drop_view()
        self.splitter.setSizes([250, 750])
        self.new_button.clicked.connect(self.setup_file_drop_view)
        self.transcription_thread = None
        self.llm_thread = None

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

    @Slot(str)
    def handle_file_selected(self, file_path):
        if not self.api_key:
            QMessageBox.critical(self, "APIキー未設定", "環境変数 `OPENAI_API_KEY` が設定されていません。")
            return
        file_name = Path(file_path).name
        self.minutes_list.insertItem(0, file_name)
        self.minutes_list.setCurrentRow(0)
        self.minutes_view = MinutesViewWidget()
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

    @Slot(str)
    def on_llm_error(self, error_message):
        self.minutes_view.show_processing_status(f"LLMエラー:\n\n{error_message}", "summary")
        self.minutes_view.show_processing_status("", "decisions")
        self.minutes_view.show_processing_status("", "todo")
        if self.llm_thread and self.llm_thread.isRunning():
            self.llm_thread.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
