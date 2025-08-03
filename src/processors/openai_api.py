import os
from openai import OpenAI
from .base import BaseProcessor

class OpenAIApiProcessor(BaseProcessor):
    """
    A processor that uses the OpenAI API for transcription.
    """

    def __init__(self, api_key: str = None):
        """
        Initializes the OpenAI client.

        Args:
            api_key: The OpenAI API key. If not provided, it will be
                     read from the OPENAI_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable or pass it to the constructor.")

        self.client = OpenAI(api_key=self.api_key)

    def transcribe(self, file_path: str) -> str:
        """
        Transcribes the audio file using the OpenAI Whisper API.

        Args:
            file_path: The path to the audio file.

        Returns:
            The transcribed text.
        """
        try:
            with open(file_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
            return transcription.text
        except Exception as e:
            # In a real app, you'd want more robust error handling
            print(f"An error occurred during transcription: {e}")
            return f"Error: {e}"
