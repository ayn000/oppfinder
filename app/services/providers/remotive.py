import httpx

from .base import Provider, RawJob, parse_iso, strip_html

API_URL = "https://remotive.com/api/remote-jobs"


class RemotiveProvider(Provider):
    name = "remotive"
    label = "Remotive (télétravail, international)"
    zones = None  # remote → every zone

    async def fetch(
        self, keywords: list[str], location: str | None, countries: list[str] | None = None
    ) -> list[RawJob]:
        params = {"search": " ".join(keywords[:4]), "limit": 50}
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(API_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()

        jobs: list[RawJob] = []
        for item in payload.get("jobs", []):
            url = item.get("url", "")
            title = item.get("title", "")
            if not url or not title:
                continue
            jobs.append(
                RawJob(
                    title=title,
                    url=url,
                    source=self.name,
                    company=item.get("company_name", ""),
                    location=item.get("candidate_required_location") or "Télétravail",
                    description=strip_html(item.get("description", ""))[:6000],
                    contract_type=item.get("job_type") or "",
                    published_at=parse_iso(item.get("publication_date")),
                )
            )
        return jobs
