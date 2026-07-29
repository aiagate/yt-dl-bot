"""Typed errors exposed by the application-service boundary."""


class ApplicationServiceError(Exception):
    def __init__(self, message: str, *, original_error: BaseException) -> None:
        super().__init__(message)
        self.original_error = original_error


class VideoCheckError(ApplicationServiceError):
    """Video readiness or metadata validation failed."""


class VideoDownloadError(ApplicationServiceError):
    """A video download failed."""


class HighlightCreationError(ApplicationServiceError):
    """Highlight metadata or chat processing failed."""


class ArtifactStorageError(ApplicationServiceError):
    """Moving an application artifact failed."""
