class ContractReviewError(Exception):
    """A user-facing contract review error."""


class UnsupportedDocumentError(ContractReviewError):
    """The uploaded document cannot be safely parsed."""


class AIReviewError(ContractReviewError):
    """The configured AI provider did not return a valid review."""

