"""Unit tests for STRAT-202: Upload Abstraction Layer."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stratum.backends.full_content import FullContentBackend
from stratum.backends.metadata_only import MetadataOnlyBackend
from stratum.config import UploadConfig
from stratum.exceptions import FileRecordNotProcessedException
from stratum.models import FileRecord, FileType, UploadResult

DT = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
SCAN_RUN_ID = "2024-03-15T10:30:00+00:00"
FAKE_VERSION = "1.0"


def make_complete_record(**kwargs) -> FileRecord:
    defaults = dict(
        path=Path("/home/user/docs/report.pdf"),
        size_bytes=2048,
        mtime=DT,
        atime=DT,
        ext="pdf",
        content_hash="abc123def456",
        file_type=FileType.DOCUMENT,
        is_duplicate=False,
    )
    defaults.update(kwargs)
    return FileRecord(**defaults)


def make_config(**kwargs) -> UploadConfig:
    defaults = dict(
        bucket="test-bucket",
        prefix="stratum/",
        region="us-east-1",
        profile=None,
    )
    defaults.update(kwargs)
    return UploadConfig(**defaults)


# ---------------------------------------------------------------------------
# MetadataOnlyBackend — _generate_upload_content
# ---------------------------------------------------------------------------


class TestGenerateUploadContent:
    def setup_method(self):
        self.config = make_config()
        self.record = make_complete_record()

    def _make_backend(self) -> MetadataOnlyBackend:
        return MetadataOnlyBackend(config=self.config, scan_run_id=SCAN_RUN_ID)

    def test_returns_bytes(self):
        with patch("stratum.backends.metadata_only._read_version", return_value=FAKE_VERSION):
            content = self._make_backend()._generate_upload_content(self.record)
        assert isinstance(content, bytes)

    def test_is_valid_json(self):
        with patch("stratum.backends.metadata_only._read_version", return_value=FAKE_VERSION):
            content = self._make_backend()._generate_upload_content(self.record)
        assert isinstance(json.loads(content), dict)

    def test_all_required_fields_present(self):
        required = {
            "schema_version",
            "content_hash",
            "original_path",
            "filename",
            "extension",
            "size_bytes",
            "mtime",
            "atime",
            "file_type",
            "hostname",
            "scan_run_id",
            "upload_mode",
            "content_available",
        }
        with patch("stratum.backends.metadata_only._read_version", return_value=FAKE_VERSION):
            content = self._make_backend()._generate_upload_content(self.record)
        assert required.issubset(json.loads(content).keys())

    def test_content_hash_matches_record(self):
        with patch("stratum.backends.metadata_only._read_version", return_value=FAKE_VERSION):
            parsed = json.loads(self._make_backend()._generate_upload_content(self.record))
        assert parsed["content_hash"] == "abc123def456"

    def test_filename_is_basename_only(self):
        with patch("stratum.backends.metadata_only._read_version", return_value=FAKE_VERSION):
            parsed = json.loads(self._make_backend()._generate_upload_content(self.record))
        assert parsed["filename"] == "report.pdf"

    def test_upload_mode_is_metadata_only(self):
        with patch("stratum.backends.metadata_only._read_version", return_value=FAKE_VERSION):
            parsed = json.loads(self._make_backend()._generate_upload_content(self.record))
        assert parsed["upload_mode"] == "metadata_only"

    def test_content_available_is_false(self):
        with patch("stratum.backends.metadata_only._read_version", return_value=FAKE_VERSION):
            parsed = json.loads(self._make_backend()._generate_upload_content(self.record))
        assert parsed["content_available"] is False

    def test_scan_run_id_matches_constructor_arg(self):
        with patch("stratum.backends.metadata_only._read_version", return_value=FAKE_VERSION):
            parsed = json.loads(self._make_backend()._generate_upload_content(self.record))
        assert parsed["scan_run_id"] == SCAN_RUN_ID

    def test_hostname_is_non_empty_string(self):
        with patch("stratum.backends.metadata_only._read_version", return_value=FAKE_VERSION):
            parsed = json.loads(self._make_backend()._generate_upload_content(self.record))
        assert isinstance(parsed["hostname"], str)
        assert len(parsed["hostname"]) > 0

    def test_hostname_comes_from_socket(self):
        with patch("stratum.backends.metadata_only._read_version", return_value=FAKE_VERSION):
            with patch(
                "stratum.backends.metadata_only.socket.gethostname",
                return_value="test-box",
            ):
                parsed = json.loads(self._make_backend()._generate_upload_content(self.record))
        assert parsed["hostname"] == "test-box"

    def test_schema_version_comes_from_version_file(self):
        with patch("stratum.backends.metadata_only._read_version", return_value="9.9") as mock_ver:
            parsed = json.loads(self._make_backend()._generate_upload_content(self.record))
        mock_ver.assert_called_once()
        assert parsed["schema_version"] == "9.9"


# ---------------------------------------------------------------------------
# MetadataOnlyBackend — upload()
# ---------------------------------------------------------------------------


class TestMetadataOnlyBackendUpload:
    def setup_method(self):
        self.config = make_config()
        self.backend = MetadataOnlyBackend(config=self.config, scan_run_id=SCAN_RUN_ID)
        self.record = make_complete_record()
        self.s3_client = MagicMock()

    def _upload(self) -> UploadResult:
        with patch("stratum.backends.metadata_only._read_version", return_value=FAKE_VERSION):
            return self.backend.upload(self.record, self.s3_client)

    def test_returns_upload_result(self):
        result = self._upload()
        assert isinstance(result, UploadResult)

    def test_result_s3_key_is_non_empty(self):
        result = self._upload()
        assert result.s3_key != ""

    def test_s3_key_contains_content_hash(self):
        result = self._upload()
        assert "abc123def456" in result.s3_key

    def test_s3_key_contains_year_month(self):
        result = self._upload()
        assert "2024/03" in result.s3_key

    def test_s3_key_ends_with_json(self):
        result = self._upload()
        assert result.s3_key.endswith(".json")

    def test_put_object_called_once(self):
        self._upload()
        self.s3_client.put_object.assert_called_once()

    def test_put_object_receives_correct_bucket(self):
        self._upload()
        _, kwargs = self.s3_client.put_object.call_args
        assert kwargs["Bucket"] == "test-bucket"

    def test_put_object_content_type_is_application_json(self):
        self._upload()
        _, kwargs = self.s3_client.put_object.call_args
        assert kwargs["ContentType"] == "application/json"

    def test_put_object_body_is_bytes(self):
        self._upload()
        _, kwargs = self.s3_client.put_object.call_args
        assert isinstance(kwargs["Body"], bytes)

    def test_put_object_body_deserialises_to_dict(self):
        self._upload()
        _, kwargs = self.s3_client.put_object.call_args
        assert isinstance(json.loads(kwargs["Body"]), dict)

    def test_put_object_has_tagging_parameter(self):
        self._upload()
        _, kwargs = self.s3_client.put_object.call_args
        assert "Tagging" in kwargs

    def test_incomplete_record_raises_before_s3_call(self):
        incomplete = FileRecord(path=Path("/x.txt"), size_bytes=1, mtime=DT, atime=DT)
        with patch("stratum.backends.metadata_only._read_version", return_value=FAKE_VERSION):
            with pytest.raises(FileRecordNotProcessedException):
                self.backend.upload(incomplete, self.s3_client)
        self.s3_client.put_object.assert_not_called()


# ---------------------------------------------------------------------------
# MetadataOnlyBackend — estimated_bytes()
# ---------------------------------------------------------------------------


class TestEstimatedBytes:
    def setup_method(self):
        self.backend = MetadataOnlyBackend(config=make_config(), scan_run_id=SCAN_RUN_ID)
        self.record = make_complete_record()

    def test_returns_positive_integer(self):
        result = self.backend.estimated_bytes(self.record)
        assert isinstance(result, int)
        assert result > 0

    def test_no_io_calls(self):
        with patch("builtins.open", side_effect=AssertionError("should not read any files")):
            result = self.backend.estimated_bytes(self.record)
        assert result > 0

    def test_no_network_calls(self):
        with patch("socket.gethostname", side_effect=AssertionError("should not call socket")):
            result = self.backend.estimated_bytes(self.record)
        assert result > 0


# ---------------------------------------------------------------------------
# FullContentBackend
# ---------------------------------------------------------------------------


class TestFullContentBackend:
    def setup_method(self):
        self.backend = FullContentBackend(config=make_config(), scan_run_id=SCAN_RUN_ID)
        self.record = make_complete_record()
        self.s3_client = MagicMock()

    def test_upload_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self.backend.upload(self.record, self.s3_client)

    def test_upload_error_references_phase_9(self):
        with pytest.raises(NotImplementedError, match="[Pp]hase 9"):
            self.backend.upload(self.record, self.s3_client)

    def test_estimated_bytes_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self.backend.estimated_bytes(self.record)
