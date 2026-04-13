"""Unit tests for stratum.tagger — file type classifier (STRAT-106)."""

from stratum.models import FileType
from stratum.tagger import classify

# ---------------------------------------------------------------------------
# DOCUMENT
# ---------------------------------------------------------------------------


class TestDocumentClassification:
    def test_pdf_is_document(self):
        assert classify("pdf") == FileType.DOCUMENT

    def test_docx_is_document(self):
        assert classify("docx") == FileType.DOCUMENT

    def test_txt_is_document(self):
        assert classify("txt") == FileType.DOCUMENT

    def test_md_is_document(self):
        assert classify("md") == FileType.DOCUMENT


# ---------------------------------------------------------------------------
# MEDIA
# ---------------------------------------------------------------------------


class TestMediaClassification:
    def test_jpg_is_media(self):
        assert classify("jpg") == FileType.MEDIA

    def test_png_is_media(self):
        assert classify("png") == FileType.MEDIA

    def test_mp4_is_media(self):
        assert classify("mp4") == FileType.MEDIA

    def test_mp3_is_media(self):
        assert classify("mp3") == FileType.MEDIA

    def test_jpeg_uppercase_is_media(self):
        # Spec requires case-insensitive lookup (STRAT-106 AC: classify('photo.JPEG') → MEDIA)
        assert classify("JPEG") == FileType.MEDIA


# ---------------------------------------------------------------------------
# ARCHIVE
# ---------------------------------------------------------------------------


class TestArchiveClassification:
    def test_zip_is_archive(self):
        assert classify("zip") == FileType.ARCHIVE

    def test_tar_is_archive(self):
        assert classify("tar") == FileType.ARCHIVE

    def test_dmg_is_archive(self):
        assert classify("dmg") == FileType.ARCHIVE

    def test_tar_gz_compound_extension_is_archive(self):
        # Spec intent: archive.tar.gz should classify as ARCHIVE.
        # The scanner strips the basename, yielding the compound ext "tar.gz".
        assert classify("tar.gz") == FileType.ARCHIVE


# ---------------------------------------------------------------------------
# CODE
# ---------------------------------------------------------------------------


class TestCodeClassification:
    def test_py_is_code(self):
        assert classify("py") == FileType.CODE

    def test_js_is_code(self):
        assert classify("js") == FileType.CODE

    def test_go_is_code(self):
        assert classify("go") == FileType.CODE

    def test_rs_is_code(self):
        assert classify("rs") == FileType.CODE


# ---------------------------------------------------------------------------
# OTHER (unknown and edge cases)
# ---------------------------------------------------------------------------


class TestOtherClassification:
    def test_unknown_extension_is_other(self):
        assert classify("xyz") == FileType.OTHER

    def test_unknown_does_not_raise(self):
        assert classify("notanext") == FileType.OTHER

    def test_no_extension_is_other(self):
        # Files without an extension reach classify as an empty string
        assert classify("") == FileType.OTHER


# ---------------------------------------------------------------------------
# All five FileType variants are reachable
# ---------------------------------------------------------------------------


class TestAllFileTypesReachable:
    def test_all_five_file_types_covered(self):
        reachable = {
            classify("pdf"),  # DOCUMENT
            classify("jpg"),  # MEDIA
            classify("zip"),  # ARCHIVE
            classify("py"),  # CODE
            classify("xyz"),  # OTHER
        }
        assert reachable == set(FileType)
