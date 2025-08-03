import abc

class BaseProcessor(abc.ABC):
    """
    Abstract base class for a transcription processor.
    This defines the interface for different transcription backends.
    """

    @abc.abstractmethod
    def transcribe(self, file_path: str) -> str:
        """
        Transcribes the audio file at the given path.

        Args:
            file_path: The path to the audio file.

        Returns:
            The transcribed text.

        Raises:
            NotImplementedError: If the method is not implemented by a subclass.
        """
        raise NotImplementedError
