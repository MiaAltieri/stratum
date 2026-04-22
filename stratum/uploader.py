from stratum.models import FileRecord, UploadResult
from typing import Protocol


class UploadBackend(Protocol):
    """Protocol definition for uploading to backend.

    We use a protocol here to not force strict inheritance, this enables us to have two
    protocols with different constructors."""

    def upload(record: FileRecord, s3_client) -> UploadResult: ...

    def estimated_bytes(record: FileRecord) -> int: ...
