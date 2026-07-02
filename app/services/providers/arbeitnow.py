from datetime import datetime

import httpx

from .base import Provider, RawJob, strip_html

API_URL = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowProvider(Provider):
    """No server-side search - fetches recent pages; irrelevant jobs are
    filtered out by the matching score."""

    name = "arbeitnow"
    label = "Arbeitnow (Europe, tech)"
    zones = {"fr", "europe", "world"}

    async def fetch(
        self, keywords: list[str], location: str | None, countries: list[str] | None = None
    ) -> list[RawJob]:
        jobs: list[RawJob] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for page in (1, 2):
                resp = await client.get(API_URL, params={"page": page})
                resp.raise_for_status()
                for item in resp.json().get("data", []):
                    url = item.get("url", "")
                    title = item.get("title", "")
                    if not url or not title:
                        continue
                    published = None
                    if item.get("created_at"):
                        try:
                            published = datetime.utcfromtimestamp(int(item["created_at"]))
                        except (ValueError, TypeError, OSError):
                            published = None
                    job_types = item.get("job_types") or []
                    jobs.append(
                        RawJob(
                            title=title,
                            url=url,
                            source=self.name,
                            company=item.get("company_name", ""),
                            location=item.get("location", ""),
                            description=strip_html(item.get("description", ""))[:6000],
                            contract_type=", ".join(job_types)[:30],
                            published_at=published,
                        )
                    )
        return jobs
