from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from ..auth import get_current_user, get_db
from ..models import Alert, Job, User
from ..schemas import JobOut
from .alerts import get_alert_or_404

router = APIRouter(prefix="/api", tags=["jobs"])


def get_job_or_404(job_id: int, user: User, db: DbSession) -> Job:
    job = (
        db.query(Job)
        .join(Alert, Job.alert_id == Alert.id)
        .filter(Job.id == job_id, Alert.user_id == user.id)
        .one_or_none()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Annonce introuvable")
    return job


@router.get("/alerts/{alert_id}/jobs", response_model=list[JobOut])
def list_jobs(
    alert_id: int,
    include_hidden: bool = False,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    get_alert_or_404(alert_id, user, db)
    query = db.query(Job).filter(Job.alert_id == alert_id)
    if not include_hidden:
        query = query.filter(Job.is_hidden.is_(False))
    return (
        query.order_by(Job.is_favorite.desc(), Job.score.desc(), Job.fetched_at.desc())
        .limit(500)
        .all()
    )


@router.post("/jobs/{job_id}/favorite", response_model=JobOut)
def toggle_favorite(
    job_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    job = get_job_or_404(job_id, user, db)
    job.is_favorite = not job.is_favorite
    db.commit()
    return job


@router.post("/jobs/{job_id}/hide", response_model=JobOut)
def toggle_hidden(
    job_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    job = get_job_or_404(job_id, user, db)
    job.is_hidden = not job.is_hidden
    db.commit()
    return job
