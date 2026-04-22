import json
import socket

from stratum.config import UploadConfig
from stratum.exceptions import FileRecordNotProcessedException
from stratum.helpers import _read_version
from stratum.models import FileRecord, UploadResult

BYTE_ESTIMATE = 1024


class MetadataOnlyBackend:
    def __init__(self, config: UploadConfig, scan_run_id: str) -> None:
        self.config = config
        self.scan_run_id = scan_run_id

    def _generate_upload_content(self, record) -> bytes:
        content = {
            "schema_version": _read_version(),
            "content_hash": record.content_hash,
            "original_path": record.path,
            "filename": record.path.name,
            "extension": record.ext,
            "size_bytes": record.size_bytes,
            "mtime": record.mtime,
            "atime": record.atime,
            "file_type": record.file_type,
            "hostname": socket.gethostname(),
            "scan_run_id": self.scan_run_id,
            "upload_mode": "metadata_only",
            "content_available": False,
        }

        return json.dumps(content).encode("utf-8")

    def upload(self, record: FileRecord, s3_client) -> UploadResult:
        """Uploads record to provided s3_client.

        Raises:
            ClientError
            FileRecordNotProcessedException
        """
        if not record.is_complete():
            raise FileRecordNotProcessedException("Record has not been processed.")

        # prefix here is determined by the upload config - we have just writen it out but please
        # note this is BAD STYLE and should be referenced in another way
        s3_key = f"{self.config.prefix}/{record.year_month}/{record.content_hash}.json"

        upload_content = self._generate_upload_content(record)

        # It is up to the orchestrator to decide how to handle upload failures.
        # in some cases orchestrator should retry, fail-loudly(i.e. go boom), log failure and
        # continue
        # NOTE the above approach goes against what is described in phase2. But this is the way
        # I decided to do this - because I don't want to abstract errors, this introduces
        # potentially difficult maintence
        s3_client.put_content(
            Bucket=self.config.bucket,
            Key=s3_key,
            Body=upload_content,
            ContentType="json",
        )

        return UploadResult(s3_key=s3_key, bytes_transfered=self.estimated_bytes)

    def estimated_bytes(self, record: FileRecord) -> int:
        """Since we are not uploading full files we return a constant"""
        return BYTE_ESTIMATE
