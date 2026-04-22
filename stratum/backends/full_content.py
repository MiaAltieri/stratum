from stratum.config import UploadConfig
from stratum.models import FileRecord, UploadResult


class FullContentBackend:
    def __init__(self, config: UploadConfig, scan_run_id: str) -> None:
        self.config = config
        self.scan_run_id = scan_run_id

    def upload(self, record: FileRecord, s3_client) -> UploadResult:
        raise NotImplementedError("Waiting for Phase 9 to implement")

    def estimated_bytes(self, record: FileRecord) -> int:
        raise NotImplementedError("Waiting for Phase 9 to implement")
