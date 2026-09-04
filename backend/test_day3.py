import asyncio
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.services.greenhouse import fetch_jobs_from_greenhouse, clean_html

async def test_day3():
    print("Testing HTML Cleaner...")
    dirty = "<div>Hello &amp; <b>World</b>!</div>\n\n<p>Welcome</p>"
    clean = clean_html(dirty)
    assert clean == "Hello & World ! Welcome", f"Got: {clean}"
    print("[PASSED]: HTML cleaner works")

    print("\nTesting Greenhouse API Fetch (Discord board)...")
    try:
        jobs = await fetch_jobs_from_greenhouse("discord")
        print(f"[PASSED]: Fetched {len(jobs)} jobs from Discord's Greenhouse board.")
        if jobs:
            print("\nSample Job:")
            print(f"Title: {jobs[0]['title']}")
            print(f"Location: {jobs[0]['location']}")
            print(f"URL: {jobs[0]['url']}")
            print(f"Description snippet: {jobs[0]['description'][:100]}...")
    except Exception as e:
        print(f"[FAILED]: Failed to fetch from Greenhouse: {e}")

if __name__ == "__main__":
    asyncio.run(test_day3())
