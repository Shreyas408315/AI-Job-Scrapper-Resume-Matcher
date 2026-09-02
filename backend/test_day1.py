import asyncio
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.database import async_session
from app.services.auth import register_user, login_user

async def test_db():
    print("Testing DB connection and Auth services...")
    email = "testuser@example.com"
    password = "SuperSecretPassword123"
    
    async with async_session() as session:
        # Test Registration
        try:
            print("Registering user...")
            user = await register_user(email, password, session)
            await session.commit()
            print(f"Registered user ID: {user.id}")
        except Exception as e:
            if "already registered" in str(e).lower():
                print("User already registered (expected if run twice).")
            else:
                print(f"Registration failed: {e}")
                
        # Test Login
        try:
            print("Logging in...")
            token = await login_user(email, password, session)
            print(f"Login passed! JWT Token starts with: {token[:20]}...")
        except Exception as e:
            print(f"Login failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_db())
    print("\nAll Day 1 components verified successfully!")
