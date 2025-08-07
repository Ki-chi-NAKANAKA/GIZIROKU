from PySide6.QtCore import QSettings

class SettingsManager:
    """
    Manages application settings using QSettings.
    """
    ORGANIZATION_NAME = "JulesApp"
    APPLICATION_NAME = "MinutesGenerator"

    def __init__(self):
        self.settings = QSettings(self.ORGANIZATION_NAME, self.APPLICATION_NAME)

    # --- OpenAI API Key ---
    def get_openai_api_key(self) -> str:
        return self.settings.value("openai/api_key", "")

    def set_openai_api_key(self, api_key: str):
        self.settings.setValue("openai/api_key", api_key)

    # --- Ollama Host ---
    def get_ollama_host(self) -> str:
        return self.settings.value("ollama/host", "http://localhost:11434")

    def set_ollama_host(self, host: str):
        self.settings.setValue("ollama/host", host)

    # --- Ollama Model ---
    def get_ollama_model(self) -> str:
        return self.settings.value("ollama/model", "llama3")

    def set_ollama_model(self, model: str):
        self.settings.setValue("ollama/model", model)
