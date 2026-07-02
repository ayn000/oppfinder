from datetime import timedelta

import httpx

from ...config import settings
from ...models import utcnow
from .base import Provider, RawJob, parse_iso, strip_html

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

# publieeDepuis only accepts these values (days)
_ALLOWED_FRESHNESS = (1, 3, 7, 14, 31)


class FranceTravailProvider(Provider):
    name = "france_travail"
    label = "France Travail (France, tous secteurs)"
    zones = {"fr", "europe", "world"}

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expires = utcnow()

    def available(self) -> bool:
        return bool(settings.ft_client_id and settings.ft_client_secret)

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        if self._token and utcnow() < self._token_expires:
            return self._token
        resp = await client.post(
            TOKEN_URL,
            params={"realm": "/partenaire"},
            data={
                "grant_type": "client_credentials",
                "client_id": settings.ft_client_id,
                "client_secret": settings.ft_client_secret,
                "scope": "api_offresdemploiv2 o2dsoffre",
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        # refresh one minute before actual expiry
        self._token_expires = utcnow() + timedelta(seconds=int(payload.get("expires_in", 1200)) - 60)
        return self._token

    async def fetch(
        self, keywords: list[str], location: str | None, countries: list[str] | None = None
    ) -> list[RawJob]:
        freshness = next((d for d in _ALLOWED_FRESHNESS if d >= settings.job_retention_days), 31)
        async with httpx.AsyncClient(timeout=25) as client:
            token = await self._get_token(client)
            resp = await client.get(
                SEARCH_URL,
                headers={"Authorization": f"Bearer {token}"},
                params={
                    # comma-separated keywords, max 7 accepted by the API
                    "motsCles": ",".join(k.replace(",", " ") for k in keywords[:7]),
                    "range": "0-49",
                    "publieeDepuis": freshness,
                },
            )
            if resp.status_code == 204:  # no results
                return []
            if resp.status_code not in (200, 206):  # 206 = partial range, still valid
                resp.raise_for_status()
            payload = resp.json()

        jobs: list[RawJob] = []
        for item in payload.get("resultats", []):
            title = item.get("intitule", "")
            offer_id = item.get("id", "")
            url = (item.get("origineOffre") or {}).get("urlOrigine") or (
                f"https://candidat.francetravail.fr/offres/recherche/detail/{offer_id}" if offer_id else ""
            )
            if not url or not title:
                continue
            jobs.append(
                RawJob(
                    title=title,
                    url=url,
                    source=self.name,
                    company=(item.get("entreprise") or {}).get("nom", ""),
                    location=(item.get("lieuTravail") or {}).get("libelle", ""),
                    description=strip_html(item.get("description", ""))[:6000],
                    contract_type=(item.get("typeContrat") or "").lower(),
                    published_at=parse_iso(item.get("dateCreation")),
                )
            )
        return jobs
