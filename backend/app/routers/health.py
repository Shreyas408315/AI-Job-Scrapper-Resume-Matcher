"""
Health check endpoint — verifies the API is running.

This is the ONLY endpoint that is both public and doesn't require auth.
Useful for:
- Docker HEALTHCHECK
- Load balancer probes
- Quick "is it up?" checks during development
"""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/api/health")
async def health_check():
    """Return a simple health status. No auth required."""
    return {"status": "healthy", "service": "AI Job Scraper & Resume Matcher"}
