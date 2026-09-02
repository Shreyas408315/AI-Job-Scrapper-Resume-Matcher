"""
Resume router — endpoints for uploading, listing, and deleting resumes.

SECURITY:
- All routes here require the user to be authenticated (via get_current_user).
- Deletion is strictly scoped to the authenticated user's own resumes.
- PII Protection: Our response schemas deliberately exclude the `extracted_text`
  so it isn't accidentally leaked back in the JSON responses.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.resume import ResumeResponse, ResumeUploadResponse
from app.services.resume import delete_resume, get_user_resumes, process_and_store_resume

router = APIRouter(prefix="/api/resumes", tags=["Resumes"])


@router.post("/upload", response_model=ResumeUploadResponse, status_code=201)
async def upload_resume(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a resume (PDF or DOCX).
    
    The file is validated, its text is extracted, an embedding is generated
    via the LLM provider, and the result is stored in the vector database.
    """
    resume = await process_and_store_resume(file, current_user, db)
    
    return ResumeUploadResponse(
        id=resume.id,
        filename=resume.filename
    )


@router.get("/me", response_model=list[ResumeResponse])
async def list_my_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a list of all resumes uploaded by the authenticated user.
    """
    resumes = await get_user_resumes(current_user, db)
    
    # We populate the has_embedding boolean manually for the Pydantic schema
    # by checking if the vector is not None
    response_list = []
    for r in resumes:
        response_list.append(ResumeResponse(
            id=r.id,
            filename=r.filename,
            file_type=r.file_type,
            uploaded_at=r.uploaded_at,
            has_embedding=(r.embedding is not None)
        ))
        
    return response_list


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_resume(
    resume_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a resume. 
    
    Also permanently deletes all associated data (extracted text, vectors, matches)
    due to database cascade constraints.
    """
    deleted = await delete_resume(resume_id, current_user, db)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found or you don't have permission to delete it."
        )
    
    return None
