"""Typed failures for the artifact store.

Callers can catch ArtifactStoreError for any store refusal. The store
does not rewrite an existing object when one of these is raised.
"""

from __future__ import annotations


class ArtifactStoreError(Exception):
    """Base class for artifact-store failures."""


class CanonicalError(ArtifactStoreError):
    """Value cannot be encoded as canonical JSON."""


class SchemaValidationError(ArtifactStoreError):
    """Instance does not satisfy a local JSON Schema."""

    def __init__(self, schema_name: str, detail: str) -> None:
        self.schema_name = schema_name
        self.detail = detail
        super().__init__(f"{schema_name}: {detail}")


class SchemaError(ArtifactStoreError):
    """A schema file is missing or is not itself a valid schema."""


class DigestMismatchError(ArtifactStoreError):
    """Caller-supplied id or content_digest does not match the payload."""


class MutationError(ArtifactStoreError):
    """Write-once store refused different bytes for an existing id."""

    def __init__(self, artifact_id: str) -> None:
        self.artifact_id = artifact_id
        super().__init__(
            f"artifact {artifact_id} is already stored with different bytes"
        )


class TamperError(ArtifactStoreError):
    """Stored bytes failed the hash or canonical-encoding check."""

    def __init__(self, artifact_id: str, detail: str) -> None:
        self.artifact_id = artifact_id
        self.detail = detail
        super().__init__(f"tampered artifact {artifact_id}: {detail}")


class MissingParentError(ArtifactStoreError):
    """A parent content digest does not resolve to a stored artifact."""

    def __init__(self, content_digest: str) -> None:
        self.content_digest = content_digest
        super().__init__(f"missing parent {content_digest}")


class CycleError(ArtifactStoreError):
    """Parent links would form a cycle in the evidence DAG."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class ArtifactNotFoundError(ArtifactStoreError):
    """No artifact is stored for this reference."""

    def __init__(self, artifact_id: str) -> None:
        self.artifact_id = artifact_id
        super().__init__(f"artifact not found: {artifact_id}")


class InvalidReferenceError(ArtifactStoreError):
    """Reference is not a lowercase hex id or a sha256 content digest."""


class RightsError(ArtifactStoreError):
    """Base class for dataset rights-transition failures."""


class DatasetError(Exception):
    """Base class for dataset pipeline refusals. Nothing partial is a success."""


class IllegalTransitionError(RightsError):
    """The dataset table has no edge for this state and event."""

    def __init__(self, from_state: str, event: str) -> None:
        self.from_state = from_state
        self.event = event
        super().__init__(f"no dataset transition from {from_state} on {event}")


class TransitionNotImplemented(RightsError):
    """The edge is in the spec table and is not executed by this task."""

    def __init__(self, from_state: str, event: str) -> None:
        self.from_state = from_state
        self.event = event
        super().__init__(
            f"dataset transition {from_state} on {event} is not implemented"
        )


class LicenseEvidenceError(RightsError):
    """The rights guard refused the transition for lack of license evidence."""


class NeedsHumanDecision(RightsError):
    """The license is ambiguous. The item stays in its current state."""


class SourceContentError(RightsError):
    """A rights artifact included program text or an unknown field."""


class GuardError(DatasetError):
    """The event's guard rejected the transition. No artifact was written."""


class InventoryError(DatasetError):
    """The inventory document does not match the T06 unit contract."""


class PolicyError(DatasetError):
    """A unit's rights flags are looser than the approved defaults."""


class AcquireError(DatasetError):
    """A pinned blob could not be fetched or did not match its blob sha."""


class NormalizeError(DatasetError):
    """Deterministic normalization refused one unit. The reason is a token."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)
