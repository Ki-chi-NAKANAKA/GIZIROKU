from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QLabel,
)
from .settings_manager import SettingsManager

class SettingsDialog(QDialog):
    """
    A dialog for editing application settings.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setModal(True)
        self.resize(500, 200)

        self.settings_manager = SettingsManager()

        # --- Layouts ---
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # --- Widgets ---
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)

        self.ollama_host_edit = QLineEdit()
        self.ollama_model_edit = QLineEdit()

        form_layout.addRow("OpenAI APIキー:", self.api_key_edit)
        form_layout.addRow("Ollama ホスト:", self.ollama_host_edit)
        form_layout.addRow("Ollama モデル名:", self.ollama_model_edit)

        main_layout.addLayout(form_layout)

        # --- Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.load_settings()

    def load_settings(self):
        """Load settings from SettingsManager and populate fields."""
        self.api_key_edit.setText(self.settings_manager.get_openai_api_key())
        self.ollama_host_edit.setText(self.settings_manager.get_ollama_host())
        self.ollama_model_edit.setText(self.settings_manager.get_ollama_model())

    def save_settings(self):
        """Save settings from fields to SettingsManager."""
        self.settings_manager.set_openai_api_key(self.api_key_edit.text())
        self.settings_manager.set_ollama_host(self.ollama_host_edit.text())
        self.settings_manager.set_ollama_model(self.ollama_model_edit.text())
        self.accept() # Close the dialog
