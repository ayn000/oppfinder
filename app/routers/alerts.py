import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from ..auth import get_current_user, get_db
from ..models import Alert, Job, User
from ..schemas import AlertIn, AlertOut
from ..services.providers import ALL_PROVIDERS, REGISTRY
from ..services.providers.base import ZONES
from ..services.scheduler import refresh_alert, refresh_alert_by_id

router = APIRouter(prefix="/api", tags=["alerts"])


def get_alert_or_404(alert_id: int, user: User, db: DbSession) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    return alert


def _alert_out(db: DbSession, alert: Alert) -> AlertOut:
    job_count = db.query(Job).filter(Job.alert_id == alert.id, Job.is_hidden.is_(False)).count()
    favorite_count = db.query(Job).filter(Job.alert_id == alert.id, Job.is_favorite.is_(True)).count()
    out = AlertOut.model_validate(alert)
    out.job_count = job_count
    out.favorite_count = favorite_count
    return out


def _validate_sources(sources: list[str] | None) -> list[str] | None:
    if sources is None:
        return None
    valid = [s for s in sources if s in REGISTRY]
    return valid or None


@router.get("/providers")
def list_providers(user: User = Depends(get_current_user)):
    return {
        "zones": [{"code": code, "label": z["label"]} for code, z in ZONES.items()],
        "providers": [
            {
                "name": p.name,
                "label": p.label,
                "available": p.available(),
                "zones": sorted(p.zones) if p.zones is not None else None,
            }
            for p in ALL_PROVIDERS
        ],
    }


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    alerts = db.query(Alert).filter(Alert.user_id == user.id).order_by(Alert.created_at).all()
    return [_alert_out(db, a) for a in alerts]


@router.post("/alerts", response_model=AlertOut, status_code=201)
async def create_alert(
    payload: AlertIn,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    alert = Alert(
        user_id=user.id,
        name=payload.name.strip(),
        keywords=[k.strip() for k in payload.keywords if k.strip()],
        location=payload.location.strip(),
        contract_type=payload.contract_type,
        zone=payload.zone,
        sources=_validate_sources(payload.sources),
        is_active=payload.is_active,
    )
    if not alert.keywords:
        raise HTTPException(status_code=422, detail="Au moins un mot-clé est requis")
    db.add(alert)
    db.commit()
    db.refresh(alert)
    # first fetch runs in the background so the UI stays snappy
    asyncio.create_task(refresh_alert_by_id(alert.id))
    return _alert_out(db, alert)


@router.put("/alerts/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: int,
    payload: AlertIn,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    alert = get_alert_or_404(alert_id, user, db)
    alert.name = payload.name.strip()
    alert.keywords = [k.strip() for k in payload.keywords if k.strip()]
    alert.location = payload.location.strip()
    alert.contract_type = payload.contract_type
    alert.zone = payload.zone
    alert.sources = _validate_sources(payload.sources)
    alert.is_active = payload.is_active
    db.commit()
    db.refresh(alert)
    return _alert_out(db, alert)


@router.delete("/alerts/{alert_id}", status_code=204)
def delete_alert(
    alert_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    alert = get_alert_or_404(alert_id, user, db)
    db.delete(alert)
    db.commit()


@router.post("/alerts/{alert_id}/refresh")
async def refresh_now(
    alert_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    alert = get_alert_or_404(alert_id, user, db)
    result = await refresh_alert(db, alert)
    return {"alert": _alert_out(db, alert), "result": result}
