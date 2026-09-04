import pytest

from app.services import greenhouse, job as job_service


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeAsyncClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def get(self, url):
        assert url.endswith("/v1/boards/acme/jobs?content=true")
        return self.response


@pytest.mark.asyncio
async def test_greenhouse_json_is_normalized(monkeypatch):
    response = FakeResponse(
        {
            "jobs": [
                {
                    "id": "42",
                    "title": "Backend Engineer",
                    "content": "<p>Build APIs &amp; services</p>",
                    "location": {"name": "Remote"},
                    "absolute_url": "https://example.com/jobs/42",
                },
                {"id": "not-an-id", "content": "ignored"},
                {"content": "missing id"},
            ]
        }
    )
    monkeypatch.setattr(
        greenhouse.httpx,
        "AsyncClient",
        lambda timeout: FakeAsyncClient(response),
    )

    jobs = await greenhouse.fetch_jobs_from_greenhouse("acme")

    assert jobs == [
        {
            "external_id": 42,
            "title": "Backend Engineer",
            "company": "acme",
            "url": "https://example.com/jobs/42",
            "location": "Remote",
            "description": "Build APIs & services",
        }
    ]


@pytest.mark.asyncio
async def test_unapproved_greenhouse_board_is_rejected(monkeypatch):
    monkeypatch.setattr(
        job_service,
        "fetch_jobs_from_greenhouse",
        lambda token: pytest.fail("unapproved board must not be fetched"),
    )

    with pytest.raises(ValueError, match="not allowed"):
        await job_service.sync_greenhouse_jobs("unknown-company", None)


def test_greenhouse_html_cleaner_handles_empty_input():
    assert greenhouse.clean_html("") == ""
    assert greenhouse.clean_html("<li>Python</li> &amp; SQL") == "Python & SQL"
