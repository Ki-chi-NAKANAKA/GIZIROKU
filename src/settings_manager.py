from PySide6.QtCore import QSettings


class SettingsManager:
    """Manages application settings using QSettings."""

    ORGANIZATION_NAME = "JulesApp"
    APPLICATION_NAME = "MinutesGenerator"

    def __init__(self):
        self.settings = QSettings(self.ORGANIZATION_NAME, self.APPLICATION_NAME)

    def get_openai_api_key(self) -> str | None:
        """Returns the OpenAI API key, or None if not set."""
        key = self.settings.value("openai/api_key")
        return key if key else None

    def set_openai_api_key(self, api_key: str):
        """Sets the OpenAI API key."""
        self.settings.setValue("openai/api_key", api_key)

    def get_ollama_host(self) -> str:
        """Returns the Ollama host URL."""
        return self.settings.value("ollama/host", "http://localhost:11434")

    def set_ollama_host(self, host: str):
        """Sets the Ollama host URL."""
        self.settings.setValue("ollama/host", host)

    def get_ollama_model(self) -> str:
        """Returns the Ollama model name."""
        return self.settings.value("ollama/model", "llama3")

    def set_ollama_model(self, model: str):
        """Sets the Ollama model name."""
        self.settings.setValue("ollama/model", model)
