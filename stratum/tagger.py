"""File type classifier — maps file extensions to FileType enum values."""

from stratum.models import FileType


def classify(ext: str) -> FileType:
    # Note that there are several ways to compress tar files, so lets trim that out
    if "tar" in ext:
        return FileType.ARCHIVE

    return _EXT_MAP.get(ext.lower(), FileType.OTHER)


_EXT_MAP: dict[str, FileType] = {
    # DOCUMENT
    "pdf": FileType.DOCUMENT,
    "doc": FileType.DOCUMENT,
    "docx": FileType.DOCUMENT,
    "xls": FileType.DOCUMENT,
    "xlsx": FileType.DOCUMENT,
    "ppt": FileType.DOCUMENT,
    "pptx": FileType.DOCUMENT,
    "txt": FileType.DOCUMENT,
    "md": FileType.DOCUMENT,
    "odt": FileType.DOCUMENT,
    "pages": FileType.DOCUMENT,
    # MEDIA
    "jpg": FileType.MEDIA,
    "jpeg": FileType.MEDIA,
    "png": FileType.MEDIA,
    "gif": FileType.MEDIA,
    "mp4": FileType.MEDIA,
    "mov": FileType.MEDIA,
    "mp3": FileType.MEDIA,
    "wav": FileType.MEDIA,
    "heic": FileType.MEDIA,
    "webp": FileType.MEDIA,
    "m4a": FileType.MEDIA,
    # ARCHIVE
    "zip": FileType.ARCHIVE,
    "tar": FileType.ARCHIVE,
    "bz2": FileType.ARCHIVE,
    "7z": FileType.ARCHIVE,
    "rar": FileType.ARCHIVE,
    "dmg": FileType.ARCHIVE,
    "pkg": FileType.ARCHIVE,
    # CODE
    "py": FileType.CODE,
    "js": FileType.CODE,
    "ts": FileType.CODE,
    "rs": FileType.CODE,
    "cpp": FileType.CODE,
    "c": FileType.CODE,
    "h": FileType.CODE,
    "go": FileType.CODE,
    "java": FileType.CODE,
    "rb": FileType.CODE,
    "sh": FileType.CODE,
}
