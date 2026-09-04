import io
import zipfile

import pytest
from fastapi import HTTPException
from docx import Document

from app.config import get_settings
from app.models.user import User
from app.services import resume as resume_service

class RecordingUpload:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.content = content
        self.requested_size = None

    async def read(self, size: int = -1) -> bytes:
        self.requested_size = size
        return self.content[:size]


def make_docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("Python FastAPI engineer")
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


@pytest.mark.asyncio
async def test_oversized_upload_is_read_only_to_limit():
    settings = get_settings()
    upload = RecordingUpload("large.pdf", b"x" * (settings.max_upload_bytes + 100))

    with pytest.raises(HTTPException) as error:
        await resume_service.process_and_store_resume(upload, User(), None)

    assert error.value.status_code == 413
    assert upload.requested_size == settings.max_upload_bytes + 1


@pytest.mark.asyncio
async def test_fake_pdf_is_rejected_by_content():
    upload = RecordingUpload("malicious.pdf", b"MZ" + b"x" * 100)

    with pytest.raises(HTTPException) as error:
        await resume_service.process_and_store_resume(upload, User(), None)

    assert error.value.status_code == 415
    assert "Unsupported file type" in error.value.detail


def test_docx_text_extraction():
    docx_bytes = make_docx_bytes()
    extracted = resume_service.extract_text_from_bytes(docx_bytes, "docx")

    assert resume_service.detect_file_type(docx_bytes) == "docx"
    assert extracted == "Python FastAPI engineer"


def test_invalid_docx_package_is_rejected():
    invalid_docx = io.BytesIO()
    with zipfile.ZipFile(invalid_docx, "w") as archive:
        archive.writestr("not-a-docx.txt", "invalid")

    with pytest.raises((ValueError, KeyError, zipfile.BadZipFile)):
        resume_service.extract_text_from_bytes(invalid_docx.getvalue(), "docx")
