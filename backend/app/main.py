from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from database import get_db, engine
from models import Base, SessionLog

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Token Monitor API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pricing table (USD per 1M tokens) ──────────────────────────────────────
PRICING = {
    "claude-opus-4-6":    {"input": 15.0,  "output": 75.0},
    "claude-sonnet-4-6":  {"input": 3.0,   "output": 15.0},
    "claude-haiku-4-5":   {"input": 0.8,   "output": 4.0},
    "copilot-gpt4o":      {"input": 5.0,   "output": 15.0},
    "copilot-gpt4":       {"input": 10.0,  "output": 30.0},
}

def calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING.get(model, {"input": 3.0, "output": 15.0})
    return (input_tokens / 1_000_000) * rates["input"] + \
           (output_tokens / 1_000_000) * rates["output"]


# ── Schemas ─────────────────────────────────────────────────────────────────
class LogRequest(BaseModel):
    platform:      str
    model:         str
    input_tokens:  int
    output_tokens: int
    label:         Optional[str] = None
    git_branch:    Optional[str] = None
    project:       Optional[str] = None

class LogResponse(BaseModel):
    id:            int
    platform:      str
    model:         str
    input_tokens:  int
    output_tokens: int
    cost_usd:      float
    label:         Optional[str]
    git_branch:    Optional[str]
    project:       Optional[str]
    logged_at:     datetime

    class Config:
        from_attributes = True


# ── Endpoints ────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/log", response_model=LogResponse)
def log_session(req: LogRequest, db: Session = Depends(get_db)):
    cost = calc_cost(req.model, req.input_tokens, req.output_tokens)
    log = SessionLog(
        platform=req.platform,
        model=req.model,
        input_tokens=req.input_tokens,
        output_tokens=req.output_tokens,
        cost_usd=cost,
        label=req.label,
        git_branch=req.git_branch,
        project=req.project,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@app.get("/sessions")
def get_sessions(
    platform: Optional[str] = None,
    project:  Optional[str] = None,
    limit:    int = 50,
    db: Session = Depends(get_db)
):
    q = db.query(SessionLog)
    if platform:
        q = q.filter(SessionLog.platform == platform)
    if project:
        q = q.filter(SessionLog.project == project)
    sessions = q.order_by(SessionLog.logged_at.desc()).limit(limit).all()
    return sessions


@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(
        func.sum(SessionLog.input_tokens).label("total_input"),
        func.sum(SessionLog.output_tokens).label("total_output"),
        func.sum(SessionLog.cost_usd).label("total_cost"),
        func.count(SessionLog.id).label("total_sessions"),
    ).one()

    by_platform = db.query(
        SessionLog.platform,
        func.sum(SessionLog.cost_usd).label("cost"),
        func.count(SessionLog.id).label("sessions"),
    ).group_by(SessionLog.platform).all()

    by_model = db.query(
        SessionLog.model,
        func.sum(SessionLog.input_tokens + SessionLog.output_tokens).label("tokens"),
        func.sum(SessionLog.cost_usd).label("cost"),
    ).group_by(SessionLog.model).order_by(func.sum(SessionLog.cost_usd).desc()).all()

    # Peak hour — jam dengan token terbanyak
    by_hour = db.query(
        extract("hour", SessionLog.logged_at).label("hour"),
        func.sum(SessionLog.input_tokens + SessionLog.output_tokens).label("tokens"),
    ).group_by("hour").order_by(func.sum(SessionLog.input_tokens + SessionLog.output_tokens).desc()).first()

    return {
        "total_input_tokens":  total.total_input  or 0,
        "total_output_tokens": total.total_output or 0,
        "total_cost_usd":      round(total.total_cost or 0, 6),
        "total_sessions":      total.total_sessions or 0,
        "by_platform": [
            {"platform": r.platform, "cost_usd": round(r.cost, 6), "sessions": r.sessions}
            for r in by_platform
        ],
        "by_model": [
            {"model": r.model, "tokens": r.tokens, "cost_usd": round(r.cost, 6)}
            for r in by_model
        ],
        "peak_hour": int(by_hour.hour) if by_hour else None,
    }


@app.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    log = db.query(SessionLog).filter(SessionLog.id == session_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(log)
    db.commit()
    return {"deleted": session_id}
