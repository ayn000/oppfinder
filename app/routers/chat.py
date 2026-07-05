from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DbSession

from ..auth import get_current_user, get_db
from ..config import settings
from ..models import Alert, User
from ..schemas import ChatIn
from ..services.chatbot import chat_enabled, stream_reply
from .jobs import get_job_or_404

router = APIRouter(prefix="/api", tags=["chat"])


@router.get("/chat/status")
def chat_status(user: User = Depends(get_current_user)):
    enabled = chat_enabled()
    return {"enabled": enabled, "model": settings.anthropic_model if enabled else None}


@router.post("/chat")
async def chat(
    payload: ChatIn,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    if not chat_enabled():
        raise HTTPException(status_code=503, detail="Assistant IA non configuré (ANTHROPIC_API_KEY manquante)")
    if payload.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="Le dernier message doit venir de l'utilisateur")
    job = get_job_or_404(payload.job_id, user, db)
    alert = db.get(Alert, job.alert_id)
    return StreamingResponse(
        stream_reply(job, alert, payload.messages),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
