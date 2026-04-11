from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.models import SessionLog
from app.schemas import SessionLogCreate, SessionLogResponse
from app.core.pricing import calc_cost

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionLogResponse)
def create_session(req: SessionLogCreate, db: Session = Depends(get_db)):
    cost = calc_cost(req.model, req.input_tokens, req.output_tokens)
    log = SessionLog(**req.model_dump(), cost_usd=cost)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get("", response_model=list[SessionLogResponse])
def list_sessions(
    platform: Optional[str] = None,
    project:  Optional[str] = None,
    limit:    int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(SessionLog)
    if platform:
        q = q.filter(SessionLog.platform == platform)
    if project:
        q = q.filter(SessionLog.project == project)
    return q.order_by(SessionLog.logged_at.desc()).limit(limit).all()


@router.delete("/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    log = db.query(SessionLog).filter(SessionLog.id == session_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(log)
    db.commit()
    return {"deleted": session_id}
