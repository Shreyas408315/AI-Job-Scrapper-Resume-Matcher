"""
Greenhouse API Client.

SECURITY & DESIGN DECISIONS:
- Structured Data Only: We explicitly use the boards-api (JSON) instead of scraping HTML. 
  This is far more reliable and avoids XSS or broken layouts when parsing.
- Rate Limiting/Timeouts: We set a timeout of 10s to prevent our server from hanging 
  if the Greenhouse API goes down.
"""

import html
import logging
import re

import httpx

GREENHOUSE_API_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
logger = logging.getLogger(__name__)


def clean_html(raw_html: str) -> str:
    """
    Strips HTML tags and unescapes HTML entities from a string.
    Greenhouse returns job descriptions with heavy HTML formatting. We need raw text
    so our embeddings aren't polluted with `<div>` and `<li>` tokens.
    """
    if not raw_html:
        return ""
        
    # Unescape things like &amp; to &
    text = html.unescape(raw_html)
    
    # Remove HTML tags using a regular expression
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Normalize whitespace (replace multiple spaces/newlines with a single space or newline)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


async def fetch_jobs_from_greenhouse(board_token: str) -> list[dict]:
    """
    Fetch and clean job postings from a public Greenhouse board.
    
    Args:
        board_token (str): The company's Greenhouse identifier (e.g., "openai", "stripe")
        
    Returns:
        list[dict]: A list of cleaned job dictionaries containing title, company, url, etc.
    """
    url = GREENHOUSE_API_URL.format(board_token=board_token)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()  # Will raise httpx.HTTPStatusError if 4xx/5xx
        
        data = response.json()
        
    jobs = data.get("jobs", [])
    
    cleaned_jobs = []
    for job in jobs:
        if not isinstance(job, dict) or "id" not in job:
            logger.warning("Skipping malformed Greenhouse job payload")
            continue

        try:
            external_id = int(job["id"])
        except (TypeError, ValueError):
            logger.warning("Skipping Greenhouse job with invalid external id")
            continue

        # Extract location name (Greenhouse stores it nested)
        location = job.get("location", {}).get("name", "Remote / Unspecified")
        
        # Clean the rich HTML description into raw text for embeddings
        raw_description = job.get("content", "")
        cleaned_desc = clean_html(raw_description)
        
        # Only keep jobs that have actual descriptions
        if not cleaned_desc:
            continue
            
        cleaned_jobs.append({
            "external_id": external_id,
            "title": job.get("title", "Untitled Job"),
            "company": board_token,
            "url": job.get("absolute_url", ""),
            "location": location,
            "description": cleaned_desc
        })
        
    return cleaned_jobs
