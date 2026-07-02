import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

# Zones de recherche. "adzuna" liste les pays interrogés sur l'API Adzuna
# (un endpoint par pays) quand l'alerte utilise cette zone.
ZONES: dict[str, dict] = {
    "fr": {"label": "France", "adzuna": ["fr"]},
    "europe": {
        "label": "Europe",
        "adzuna": ["fr", "gb", "de", "nl", "be", "es", "it", "at", "ch", "pl"],
    },
    "north_america": {"label": "Amérique du Nord", "adzuna": ["us", "ca"]},
    "latam": {"label": "Amérique latine", "adzuna": ["mx", "br"]},
    "apac": {"label": "Asie-Pacifique", "adzuna": ["au", "nz", "sg", "in"]},
    "africa": {"label": "Afrique", "adzuna": ["za"]},
    "world": {
        "label": "Monde entier",
        "adzuna": [
            "fr", "gb", "de", "nl", "be", "es", "it", "at", "ch", "pl",
            "us", "ca", "mx", "br", "au", "nz", "sg", "in", "za",
        ],
    },
}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", text or "")).strip()


def parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


@dataclass
class RawJob:
    title: str
    url: str
    source: str
    company: str = ""
    location: str = ""
    description: str = ""
    contract_type: str = ""
    published_at: datetime | None = field(default=None)


class Provider(ABC):
    """A job board connector. Implementations must never raise on bad payloads
    for a single job - skip the entry instead; network errors may raise and are
    handled by the caller."""

    name: str
    label: str
    zones: set[str] | None = None  # None = compatible with every zone

    def available(self) -> bool:
        return True

    def supports_zone(self, zone: str) -> bool:
        return self.zones is None or zone in self.zones

    @abstractmethod
    async def fetch(
        self, keywords: list[str], location: str | None, countries: list[str] | None = None
    ) -> list[RawJob]: ...
