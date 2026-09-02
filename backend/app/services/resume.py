"""
Resume service — handles file validation, text extraction, embedding, and storage.

SECURITY CONTROLS:
- Magic bytes validation: We use python-magic to inspect the actual bytes of the file,
  not just the .pdf or .docx extension. This prevents malicious users from uploading
  an executable renamed to .pdf.
- Size limit: We enforce the 5MB size limit to prevent Denial of Service (DoS) via
  massive file parsing, which consumes heavy CPU/RAM.
"""

import io
from uuid import UUID

import magic
import pdfplumber
from docx import Document
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.resume import Resume
from app.models.user import User
from app.services.embedding import generate_embedding

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
    
    # Read the file contents into memory
    file_bytes = await file.read()
    
    # 1. Size Validation
    if len(file_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB}MB."
        )
        
    # 2. Magic Bytes Validation
    mime_type = magic.from_buffer(file_bytes, mime=True)
    if mime_type not in ALLOWED_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Detected {mime_type}. Only PDF and DOCX are allowed."
        )
        
    file_type = ALLOWED_MIMES[mime_type]
    
    # 3. Text Extraction
    try:
        extracted_text = extract_text_from_bytes(file_bytes, file_type)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Could not extract text from file: {str(e)}"
        )
        
    if not extracted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The file appears to be empty or contains no extractable text (e.g. image-only PDF)."
        )
        
    # 4. Generate Embedding
    try:
        embedding = await generate_embedding(extracted_text)
    except Exception as e:
        # In a real app, this should be a background job, but for MVP it's sync.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to generate vector embedding from LLM provider: {str(e)}"
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
    """Extract raw text from PDF or DOCX file bytes in memory."""
    text_chunks = []
    
    if file_type == "pdf":
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_chunks.append(page_text)
                    
    elif file_type == "docx":
        doc = Document(io.BytesIO(file_bytes))
        for para in doc.paragraphs:
            text_chunks.append(para.text)
            
    return "\n".join(text_chunks)


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
