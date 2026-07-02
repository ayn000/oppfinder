from .adzuna import AdzunaProvider
from .arbeitnow import ArbeitnowProvider
from .base import Provider, RawJob
from .france_travail import FranceTravailProvider
from .remotive import RemotiveProvider

ALL_PROVIDERS: list[Provider] = [
    FranceTravailProvider(),
    AdzunaProvider(),
    RemotiveProvider(),
    ArbeitnowProvider(),
]

REGISTRY: dict[str, Provider] = {p.name: p for p in ALL_PROVIDERS}


def available_providers() -> list[Provider]:
    return [p for p in ALL_PROVIDERS if p.available()]
