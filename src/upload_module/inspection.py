import re
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path


class UploadRejectedError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class UploadBlockedError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class InspectionUnavailableError(RuntimeError):
    """Raised when the required document inspection tool is unavailable."""


@dataclass(frozen=True)
class InspectionResult:
    actual_type: str
    page_count: int | None


_PDF_ACTIVE_CONTENT = re.compile(
    rb"/(?:JavaScript|JS|Launch|EmbeddedFile|OpenAction|AA)\b",
    re.IGNORECASE,
)
_DOCX_EXTERNAL_RELATIONSHIP = re.compile(
    rb"""\bTargetMode\s*=\s*["']External["']""",
    re.IGNORECASE,
)


def inspect_upload(
    path: Path,
    *,
    max_pdf_pages: int,
    max_docx_entries: int,
    max_docx_uncompressed_bytes: int,
    max_docx_compression_ratio: int,
) -> InspectionResult:
    if max_pdf_pages <= 0:
        raise ValueError("max_pdf_pages must be greater than zero")
    if max_docx_entries <= 0:
        raise ValueError("max_docx_entries must be greater than zero")
    if max_docx_uncompressed_bytes <= 0:
        raise ValueError("max_docx_uncompressed_bytes must be greater than zero")
    if max_docx_compression_ratio <= 0:
        raise ValueError("max_docx_compression_ratio must be greater than zero")

    with path.open("rb") as source:
        signature = source.read(1024)

    if b"%PDF-" in signature:
        return _inspect_pdf(
            path,
            max_pdf_pages=max_pdf_pages,
        )
    if signature.startswith(b"PK"):
        return _inspect_docx(
            path,
            max_entries=max_docx_entries,
            max_uncompressed_bytes=max_docx_uncompressed_bytes,
            max_compression_ratio=max_docx_compression_ratio,
        )
    raise UploadRejectedError(
        "UNSUPPORTED_FILE_TYPE",
        "Only PDF and DOCX uploads are supported",
    )


def _inspect_pdf(path: Path, *, max_pdf_pages: int) -> InspectionResult:
    file_bytes = path.read_bytes()
    if _PDF_ACTIVE_CONTENT.search(file_bytes):
        raise UploadBlockedError(
            "PDF_ACTIVE_CONTENT",
            "PDF contains a disallowed active-content marker",
        )

    try:
        result = subprocess.run(
            ["pdfinfo", str(path)],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except FileNotFoundError as error:
        raise InspectionUnavailableError(
            "The pdfinfo utility is required to inspect PDF uploads"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise InspectionUnavailableError(
            "PDF inspection exceeded its time limit"
        ) from error

    if result.returncode != 0:
        raise UploadRejectedError(
            "PDF_INVALID",
            "PDF could not be opened for basic inspection",
        )

    encrypted_match = re.search(
        r"^Encrypted:\s+(yes|no)",
        result.stdout,
        re.MULTILINE | re.IGNORECASE,
    )
    if encrypted_match is None:
        raise InspectionUnavailableError(
            "pdfinfo did not report the PDF encryption status"
        )
    if encrypted_match.group(1).lower() == "yes":
        raise UploadRejectedError(
            "PDF_ENCRYPTED",
            "Password-protected PDF files are not accepted",
        )

    pages_match = re.search(r"^Pages:\s+(\d+)", result.stdout, re.MULTILINE)
    if pages_match is None:
        raise UploadRejectedError(
            "PDF_INVALID",
            "PDF page count could not be determined",
        )
    page_count = int(pages_match.group(1))

    if page_count > max_pdf_pages:
        raise UploadRejectedError(
            "PDF_PAGE_LIMIT_EXCEEDED",
            "PDF exceeds the configured page limit",
        )

    return InspectionResult(actual_type="application/pdf", page_count=page_count)


def _inspect_docx(
    path: Path,
    *,
    max_entries: int,
    max_uncompressed_bytes: int,
    max_compression_ratio: int,
) -> InspectionResult:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > max_entries:
                raise UploadRejectedError(
                    "DOCX_ENTRY_LIMIT_EXCEEDED",
                    "DOCX archive contains too many entries",
                )

            total_uncompressed_bytes = sum(entry.file_size for entry in entries)
            total_compressed_bytes = sum(entry.compress_size for entry in entries)
            if total_uncompressed_bytes > max_uncompressed_bytes:
                raise UploadRejectedError(
                    "DOCX_EXPANSION_LIMIT_EXCEEDED",
                    "DOCX archive expands beyond the configured limit",
                )
            if (
                total_uncompressed_bytes > 0
                and (
                    total_compressed_bytes == 0
                    or total_uncompressed_bytes
                    > total_compressed_bytes * max_compression_ratio
                )
            ):
                raise UploadRejectedError(
                    "DOCX_COMPRESSION_RATIO_EXCEEDED",
                    "DOCX archive exceeds the configured compression ratio",
                )

            names = {entry.filename for entry in entries}
            if (
                "[Content_Types].xml" not in names
                or "word/document.xml" not in names
            ):
                raise UploadRejectedError(
                    "DOCX_INVALID_PACKAGE",
                    "ZIP archive is not a valid DOCX package",
                )

            if any(entry.flag_bits & 0x1 for entry in entries):
                raise UploadRejectedError(
                    "DOCX_ENCRYPTED",
                    "Encrypted DOCX archives are not accepted",
                )

            if any(
                name.lower().endswith("vbaproject.bin")
                or name.startswith("word/embeddings/")
                for name in names
            ):
                raise UploadBlockedError(
                    "DOCX_ACTIVE_CONTENT",
                    "DOCX contains a macro or embedded object",
                )

            relationship_files = [
                name
                for name in names
                if name.endswith(".rels")
            ]
            for name in relationship_files:
                with archive.open(name) as relationship_file:
                    relationship_data = relationship_file.read(1_048_577)
                if len(relationship_data) > 1_048_576:
                    raise UploadRejectedError(
                        "DOCX_RELATIONSHIPS_TOO_LARGE",
                        "DOCX relationship metadata exceeds its inspection limit",
                    )
                if _DOCX_EXTERNAL_RELATIONSHIP.search(relationship_data):
                    raise UploadBlockedError(
                        "DOCX_EXTERNAL_RELATIONSHIP",
                        "DOCX contains an external relationship",
                    )
    except (zipfile.BadZipFile, OSError) as error:
        raise UploadRejectedError(
            "DOCX_INVALID_PACKAGE",
            "DOCX archive could not be opened",
        ) from error

    return InspectionResult(
        actual_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        page_count=None,
    )
