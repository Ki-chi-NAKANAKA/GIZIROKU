import ollama

class OllamaProcessor:
    """
    A processor for generating text using a local Ollama server.
    """

    def __init__(self, host: str = "http://localhost:11434"):
        """
        Initializes the Ollama client.

        Args:
            host: The URL of the Ollama server.
        """
        try:
            self.client = ollama.Client(host=host)
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Ollama client at {host}: {e}")

    def generate(self, model: str, system_prompt: str, user_text: str) -> str:
        """
        Generates text using the specified model and prompts.

        Args:
            model: The name of the model to use (e.g., 'llama3').
            system_prompt: The system-level instruction for the model.
            user_text: The user-provided text (e.g., the transcript).

        Returns:
            The generated text from the model.
        """
        try:
            response = self.client.chat(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_text,
                    },
                ],
            )
            return response["message"]["content"]
        except Exception as e:
            # More specific error handling could be added here
            # (e.g., for connection errors, model not found, etc.)
            print(f"An error occurred during text generation: {e}")
            return f"Error communicating with Ollama: {e}"
