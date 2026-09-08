"""
Resume service — handles file validation, text extraction, embedding, and storage.

SECURITY CONTROLS:
- Magic bytes validation: We use python-magic to inspect the actual bytes of the file,
  not just the .pdf or .docx extension. This prevents malicious users from uploading
  an executable renamed to .pdf.
- Size limit: We enforce the 5MB size limit to prevent Denial of Service (DoS) via
  massive file parsing, which consumes heavy CPU/RAM.
- Resume-likeness gate: Question PDFs and interview papers are not legitimate
  resumes, and they should be rejected before embedding so the matching ranker
  never learns from them and hallucinated high-confidence scores disappear.
"""

import io
import logging
import re
import zipfile
from uuid import UUID

import magic
import pdfplumber
from docx import Document
from fastapi import HTTPException, UploadFile, status
from pypdfium2 import PdfDocument
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.resume import Resume
from app.models.user import User
from app.services.embedding import generate_embedding

logger = logging.getLogger(__name__)

# Allowed MIME types mapped to our internal file_type enum strings
ALLOWED_MIMES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


async def process_and_store_resume(
    file: UploadFile,
    user: User,
    db: AsyncSession
) -> Resume:
    """
    Validate, extract text, embed, and store a resume.
    """
    settings = get_settings()
    
    # Read at most one byte beyond the limit so oversized uploads do not fill
    # memory before validation rejects them.
    file_bytes = await file.read(settings.max_upload_bytes + 1)
    
    # 1. Size Validation
    if len(file_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB}MB."
        )
        
    # 2. Magic Bytes Validation
    file_type = detect_file_type(file_bytes)
    if file_type is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Only PDF and DOCX files are allowed.",
        )
    
    # 3. Text Extraction
    try:
        extracted_text = extract_text_from_bytes(file_bytes, file_type)
    except Exception:
        logger.exception("Resume text extraction failed for uploaded file")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract text from the uploaded file.",
        )

    if not extracted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The file appears to be empty or contains no extractable text (e.g. image-only PDF)."
        )

    # 4. Resume-likeness validation
    if not looks_like_resume_text(extracted_text):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded file does not look like a resume or candidate profile. Please upload a resume, CV, or experience document.",
        )

    # 5. Generate Embedding
    try:
        embedding = await generate_embedding(extracted_text)
    except Exception:
        logger.exception("Resume embedding generation failed")
        # In a real app, this should be a background job, but for MVP it's sync.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not process the uploaded resume right now.",
        )
        
    # 5. Store in Database
    resume = Resume(
        user_id=user.id,
        filename=file.filename or "unknown",
        file_type=file_type,
        extracted_text=extracted_text,
        embedding=embedding,
    )
    db.add(resume)
    await db.flush()  # Assigns ID
    
    return resume


def extract_text_from_bytes(file_bytes: bytes, file_type: str) -> str:
    """Extract raw text from PDF or DOCX file bytes in memory.

    We keep the fast `pdfplumber` extraction as the first pass, but if it finds
    no pages or the PDF is scanned/model-generated text with a missing text layer,
    we fall back to the PDFium-backed `pypdfium2` parser already available in the
    workspace environment. That path reads the true page text range and avoids
    the false ‘all PDFs produce the same matching score’ collapse.
    """
    text_chunks = []

    if file_type == "pdf":
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text(layout=False)
                    if page_text:
                        text_chunks.append(page_text)
        except Exception:
            logger.warning("pdfplumber failed to extract PDF text")

        if not text_chunks:
            try:
                with PdfDocument(io.BytesIO(file_bytes)) as doc:
                    for idx in range(len(doc)):
                        page = doc.get_page(idx)
                        try:
                            text_page = page.get_textpage()
                            page_text = text_page.get_text_range()
                        finally:
                            try:
                                page.close()
                            except Exception:
                                pass
                        if page_text:
                            text_chunks.append(page_text)
            except Exception:
                logger.warning("pypdfium2 fallback failed to extract PDF text")

    elif file_type == "docx":
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            if "[Content_Types].xml" not in archive.namelist():
                raise ValueError("Invalid DOCX package")
        doc = Document(io.BytesIO(file_bytes))
        for para in doc.paragraphs:
            text_chunks.append(para.text)

    return "\n".join(text_chunks)


def looks_like_resume_text(text: str) -> bool:
    """
    Keep the document gate focused on true false positives without blocking
    valid resumes. A resume-like PDF usually contains one or more of these:

    1. Contact metadata: name, email, phone, location.
    2. Career content: experience, education, skills, projects, work history.
    3. Professional vocabulary: engineer, developer, backend, frontend,
       software, cloud, etc.

    A question-paper or interview-quiz PDF will often have obvious markers
    like Question / What is / Explain the / exam / quiz. Those markers are
    rejected early, but the gate never requires a strict section list that
    would silently exclude real CVs from different layouts.
    """
    if not text or not text.strip():
        return False

    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return False

    # Reject obvious question-style documents.
    low_quality_markers = [
        "question ",
        "question 1",
        "questionnaire",
        "interview",
        "quiz",
        "exam",
        "assessment",
        "answers:",
        "what is",
        "which of the following",
        "explain the",
        "multiple choice",
    ]
    if any(marker in normalized.lower() for marker in low_quality_markers):
        return False

    # A resume should reveal enough shape to be vectorized safely.
    # Positive scoring is softer than the earlier hard two-signal gate.
    evidence = 0

    # Contact evidence
    if re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", normalized):
        evidence += 1
    if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", normalized):
        evidence += 1
    if re.search(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b", normalized):
        evidence += 1

    # Section and experience evidence
    resume_patterns = [
        r"\b(experience|worked|employment|internship|professional|career)\b",
        r"\b(education|degree|university|school|college|masters|bachelor)\b",
        r"\b(skills|technologies|tools|experience with|proficient|expertise)\b",
        r"\b(projects?|portfolio|built|developed|implementation)\b",
        r"\b(company|organization|organizations|team|worked at|role|lead)\b",
        r"\b(resume|cv|developer|engineer|software|backend|frontend|python|sql)\b",
    ]
    for pattern in resume_patterns:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            evidence += 1

    # Be generous: a real resume can be short and still clear.
    # A minimum of 2 signals should allow it through; 1 signal is not enough.
    return evidence >= 2


def detect_file_type(file_bytes: bytes) -> str | None:
    """Detect supported types from file content, not the filename extension."""
    mime_type = magic.from_buffer(file_bytes, mime=True)

    if mime_type == "application/pdf" and file_bytes.startswith(b"%PDF-"):
        return "pdf"

    if zipfile.is_zipfile(io.BytesIO(file_bytes)):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
                names = set(archive.namelist())
        except (OSError, zipfile.BadZipFile):
            return None

        if "[Content_Types].xml" in names and "word/document.xml" in names:
            return "docx"

    return None


async def get_user_resumes(user: User, db: AsyncSession) -> list[Resume]:
    """Retrieve all resumes uploaded by the current user."""
    query = select(Resume).where(Resume.user_id == user.id).order_by(Resume.uploaded_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def delete_resume(resume_id: UUID, user: User, db: AsyncSession) -> bool:
    """
    Delete a specific resume. Verifies the resume belongs to the requesting user.
    Returns True if deleted, False if not found.
    """
    query = select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id)
    result = await db.execute(query)
    resume = result.scalar_one_or_none()
    
    if not resume:
        return False
        
    await db.delete(resume)
    # The SQLAlchemy relationship cascade (and DB ON DELETE CASCADE) will 
    # automatically remove any Matches associated with this resume.
    return True
