class BodhiECGException(Exception):
    """Base exception class for BodhiECG application."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class OCRError(BodhiECGException):
    """Raised when OCR processing fails fatally."""
    pass

class ClassificationError(BodhiECGException):
    """Raised when document classification fails."""
    pass

class ExtractionException(BodhiECGException):
    """Raised when structured entity extraction fails."""
    pass

class ValidationException(BodhiECGException):
    """Raised when Knowledge Object validation fails."""
    pass

class GraphDatabaseError(BodhiECGException):
    """Raised when FalkorDB graph operations fail."""
    pass
