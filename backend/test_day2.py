import asyncio
import sys
import io

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.database import async_session
from app.services.auth import register_user, login_user
from app.services.resume import process_and_store_resume, get_user_resumes, delete_resume
from app.models.user import User
from fastapi import UploadFile

# Create a minimal valid PDF in memory
minimal_pdf_bytes = (
    b"%PDF-1.0\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
    b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n"
    b"0000000102 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n149\n%EOF\n"
)

# Mock UploadFile
class MockUploadFile:
    def __init__(self, filename, content):
        self.filename = filename
        self.content = content
        
    async def read(self):
        return self.content

async def test_day2():
    print("Testing Day 2 components (Resume processing)...")
    email = "day2tester@example.com"
    password = "SuperSecretPassword123"
    
    async with async_session() as session:
        # Create a user to own the resume
        try:
            user = await register_user(email, password, session)
            await session.commit()
            print(f"Created user: {user.email}")
        except Exception:
            # Re-fetch if already exists
            from sqlalchemy import select
            user = (await session.execute(select(User).where(User.email == email))).scalar_one()
            print(f"Using existing user: {user.email}")
            
        print("\n--- Testing Magic Bytes Validation ---")
        bad_file = MockUploadFile("malicious.pdf", b"MZ\x90\x00\x03\x00\x00\x00 This is actually an exe")
        try:
            await process_and_store_resume(bad_file, user, session)
            print("[FAILED]: Did not catch invalid magic bytes")
        except Exception as e:
            if "Unsupported file type" in str(e):
                print("[PASSED]: Caught invalid magic bytes correctly")
            else:
                print(f"[FAILED] with unexpected error: {e}")
                
        print("\n--- Testing Size Validation ---")
        huge_file = MockUploadFile("huge.pdf", b"0" * (6 * 1024 * 1024)) # 6MB
        try:
            await process_and_store_resume(huge_file, user, session)
            print("[FAILED]: Did not catch oversized file")
        except Exception as e:
            if "File too large" in str(e):
                print("[PASSED]: Caught oversized file correctly")
            else:
                print(f"[FAILED] with unexpected error: {e}")

        print("\n--- Testing PDF processing (up to LLM step) ---")
        good_file = MockUploadFile("real.pdf", minimal_pdf_bytes)
        try:
            await process_and_store_resume(good_file, user, session)
            print("[FAILED]: PDF processing succeeded but LLM should have failed (no API key)")
        except Exception as e:
            if "empty or contains no extractable text" in str(e) or "LLM provider" in str(e):
                print("[PASSED]: File validated and reached extraction/LLM phase correctly")
            else:
                print(f"[FAILED] with unexpected error: {e}")
                
        print("\n--- Testing Resume Listing ---")
        resumes = await get_user_resumes(user, session)
        print(f"[PASSED]: Retrieved {len(resumes)} resumes for user")
        
if __name__ == "__main__":
    asyncio.run(test_day2())
    print("\nDay 2 tests finished.")
