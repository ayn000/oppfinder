import logging

import httpx

from ...config import settings
from .base import Provider, RawJob, parse_iso, strip_html

logger = logging.getLogger("oppfinder.adzuna")

API_URL_TEMPLATE = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"

_CONTRACT_MAP = {"permanent": "cdi", "contract": "cdd"}


class AdzunaProvider(Provider):
    """Adzuna covers ~19 countries with one endpoint per country - this is the
    engine behind the international search zones. For multi-country zones we
    query each country sequentially with a smaller page size; a failing
    country is skipped instead of failing the whole refresh."""

    name = "adzuna"
    label = "Adzuna (multi-pays, tous secteurs)"
    zones = None  # every zone

    def available(self) -> bool:
        return bool(settings.adzuna_app_id and settings.adzuna_app_key)

    async def fetch(
        self, keywords: list[str], location: str | None, countries: list[str] | None = None
    ) -> list[RawJob]:
        countries = countries or ["fr"]
        multi = len(countries) > 1
        params_base = {
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_app_key,
            "results_per_page": 20 if multi else 50,
            "what_or": " ".join(keywords[:8]),
            "max_days_old": max(settings.job_retention_days, 1),
            "content-type": "application/json",
        }
        jobs: list[RawJob] = []
        async with httpx.AsyncClient(timeout=25) as client:
            for country in countries:
                params = dict(params_base)
                # free-text "where" only makes sense within a single country
                if location and not multi:
                    params["where"] = location
                try:
                    resp = await client.get(API_URL_TEMPLATE.format(country=country), params=params)
                    resp.raise_for_status()
                    payload = resp.json()
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning("Adzuna %s failed: %r", country, exc)
                    continue

                for item in payload.get("results", []):
                    url = item.get("redirect_url", "")
                    title = item.get("title", "")
                    if not url or not title:
                        continue
                    loc = (item.get("location") or {}).get("display_name", "")
                    if multi:
                        loc = f"{loc} ({country.upper()})" if loc else country.upper()
                    jobs.append(
                        RawJob(
                            title=strip_html(title),
                            url=url,
                            source=self.name,
                            company=(item.get("company") or {}).get("display_name", ""),
                            location=loc,
                            description=strip_html(item.get("description", ""))[:6000],
                            contract_type=_CONTRACT_MAP.get(item.get("contract_type") or "", ""),
                            published_at=parse_iso(item.get("created")),
                        )
                    )
        return jobs
