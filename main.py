import sys
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
from PySide6.QtCore import Qt, Signal, Slot
from pathlib import Path


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

        # Top bar with tabs and export button
        top_bar_layout = QHBoxLayout()
        self.tabs = QTabWidget()
        self.export_button = QPushButton("エクスポート▼")

        top_bar_layout.addWidget(self.tabs)
        top_bar_layout.addWidget(self.export_button)
        layout.addLayout(top_bar_layout)

        # Create tabs
        self.summary_edit = QTextEdit()
        self.decisions_edit = QTextEdit()
        self.todo_edit = QTextEdit()
        self.full_text_edit = QTextEdit()

        self.tabs.addTab(self.summary_edit, "要約")
        self.tabs.addTab(self.decisions_edit, "決定事項")
        self.tabs.addTab(self.todo_edit, "ToDo")
        self.tabs.addTab(self.full_text_edit, "全文")

    def set_full_text(self, text):
        self.full_text_edit.setPlainText(text)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("議事録自動生成アプリ")
        self.resize(1024, 768)

        # Main layout
        main_widget = QWidget()
        self.main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        # Top bar
        top_bar_layout = QHBoxLayout()
        self.new_button = QPushButton("[+] 新規作成")
        top_bar_layout.addWidget(self.new_button)
        top_bar_layout.addStretch()
        self.main_layout.addLayout(top_bar_layout)

        # Splitter for the main content area
        self.splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.splitter)

        # Left pane: List of past minutes
        self.minutes_list = QListWidget()
        self.minutes_list.addItems(["2025-08-01 定例会", "2025-07-25 A案件...", "2025-07-18 Bプロ..."])
        self.splitter.addWidget(self.minutes_list)

        # Right pane: Initially the file drop area
        self.setup_file_drop_view()

        # Adjust splitter initial sizes
        self.splitter.setSizes([250, 750])

        # --- Connections ---
        self.new_button.clicked.connect(self.setup_file_drop_view)

    def setup_file_drop_view(self):
        # If a view is already there, remove it
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
        print(f"File selected: {file_path}")

        # Create and set up the new minutes view
        minutes_view = MinutesViewWidget()
        minutes_view.set_full_text(f"処理対象のファイル:\n{file_path}\n\nここに文字起こし結果が表示されます。")

        # Replace the file drop widget with the minutes view
        self.splitter.widget(1).setParent(None)
        self.splitter.addWidget(minutes_view)

        # Add new item to the list
        file_name = Path(file_path).name
        self.minutes_list.insertItem(0, file_name)
        self.minutes_list.setCurrentRow(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
