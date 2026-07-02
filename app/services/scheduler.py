"""Background refresh of alerts and cleanup of stale jobs.

Runs inside the FastAPI event loop. Every cycle:
- refreshes alerts whose last refresh is older than REFRESH_INTERVAL_HOURS
- deletes non-favorite jobs not seen in the last JOB_RETENTION_DAYS
  (a still-published job gets its fetched_at bumped on refresh, so only
  delisted/stale postings age out - this keeps the database tiny)
"""
import asyncio
import logging
from datetime import timedelta

from sqlalchemy.orm import Session as DbSession

from ..config import settings
from ..database import SessionLocal
from ..models import Alert, Job, utcnow
from .matching import detect_contract, score_job
from .providers import REGISTRY, available_providers
from .providers.base import ZONES

logger = logging.getLogger("oppfinder.scheduler")

CHECK_INTERVAL_SECONDS = 1800  # look for due alerts every 30 minutes


async def scheduler_loop() -> None:
    await asyncio.sleep(5)  # let the app finish starting up
    while True:
        try:
            await refresh_due_alerts()
            cleanup_old_jobs()
        except Exception:
            logger.exception("Scheduler cycle failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def refresh_due_alerts() -> None:
    db = SessionLocal()
    try:
        cutoff = utcnow() - timedelta(hours=settings.refresh_interval_hours)
        due = (
            db.query(Alert)
            .filter(Alert.is_active.is_(True))
            .filter((Alert.last_refreshed_at.is_(None)) | (Alert.last_refreshed_at < cutoff))
            .all()
        )
        for alert in due:
            try:
                result = await refresh_alert(db, alert)
                logger.info("Alert %s (%s): %s", alert.id, alert.name, result)
            except Exception:
                logger.exception("Refresh failed for alert %s", alert.id)
    finally:
        db.close()


def _zone_of(alert: Alert) -> str:
    return alert.zone if alert.zone in ZONES else "fr"


def _providers_for(alert: Alert):
    zone = _zone_of(alert)
    providers = [p for p in available_providers() if p.supports_zone(zone)]
    if alert.sources:
        providers = [p for p in providers if p.name in alert.sources]
    return providers


async def refresh_alert(db: DbSession, alert: Alert) -> dict:
    keywords = [k.strip() for k in (alert.keywords or []) if k.strip()]
    if not keywords:
        return {"added": 0, "updated": 0}

    # Bias search queries toward the requested contract type; the stored
    # keywords used for scoring stay untouched.
    query_keywords = list(keywords)
    if alert.contract_type in ("stage", "alternance"):
        query_keywords.append(alert.contract_type)

    providers = _providers_for(alert)
    countries = ZONES[_zone_of(alert)]["adzuna"]
    results = await asyncio.gather(
        *(p.fetch(query_keywords, alert.location or None, countries) for p in providers),
        return_exceptions=True,
    )

    raw_jobs = []
    for provider, result in zip(providers, results):
        if isinstance(result, BaseException):
            logger.warning("Provider %s failed for alert %s: %r", provider.name, alert.id, result)
        else:
            raw_jobs.extend(result)

    seen_urls: set[str] = set()
    added = updated = 0
    for raw in raw_jobs:
        if not raw.url or raw.url in seen_urls:
            continue
        seen_urls.add(raw.url)
        score = score_job(keywords, raw.title, raw.description)
        if score < settings.min_score:
            continue
        existing = db.query(Job).filter_by(alert_id=alert.id, url=raw.url).one_or_none()
        if existing:
            existing.score = score
            existing.fetched_at = utcnow()
            updated += 1
        else:
            if added >= settings.max_jobs_per_alert_refresh:
                continue
            db.add(
                Job(
                    alert_id=alert.id,
                    title=raw.title[:300],
                    company=raw.company[:200],
                    location=raw.location[:200],
                    url=raw.url[:1000],
                    source=raw.source,
                    description=raw.description[:6000],
                    score=score,
                    contract_type=(raw.contract_type or detect_contract(raw.title, raw.description))[:30],
                    published_at=raw.published_at,
                )
            )
            added += 1

    alert.last_refreshed_at = utcnow()
    db.commit()
    return {"added": added, "updated": updated, "providers": [p.name for p in providers]}


async def refresh_alert_by_id(alert_id: int) -> dict | None:
    db = SessionLocal()
    try:
        alert = db.get(Alert, alert_id)
        if alert is None:
            return None
        return await refresh_alert(db, alert)
    except Exception:
        logger.exception("Background refresh failed for alert %s", alert_id)
        return None
    finally:
        db.close()


def cleanup_old_jobs() -> None:
    db = SessionLocal()
    try:
        cutoff = utcnow() - timedelta(days=settings.job_retention_days)
        deleted = (
            db.query(Job)
            .filter(Job.fetched_at < cutoff, Job.is_favorite.is_(False))
            .delete(synchronize_session=False)
        )
        db.commit()
        if deleted:
            logger.info("Cleanup: deleted %d stale jobs", deleted)
    finally:
        db.close()


def provider_registry():
    return REGISTRY
