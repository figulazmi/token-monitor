from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, timezone

from app.core.database import get_db, engine
from app.models import Base, SessionLog
from app.routers import sessions

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Token Monitor API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/stats", tags=["analytics"])
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

    by_account = db.query(
        SessionLog.account,
        func.sum(SessionLog.cost_usd).label("cost"),
        func.count(SessionLog.id).label("sessions"),
    ).group_by(SessionLog.account).order_by(func.sum(SessionLog.cost_usd).desc()).all()

    by_model = db.query(
        SessionLog.model,
        func.sum(SessionLog.input_tokens + SessionLog.output_tokens).label("tokens"),
        func.sum(SessionLog.cost_usd).label("cost"),
    ).group_by(SessionLog.model).order_by(func.sum(SessionLog.cost_usd).desc()).all()

    # extract("hour") works on PostgreSQL; silently skipped on SQLite (tests)
    try:
        by_hour = db.query(
            extract("hour", SessionLog.logged_at).label("hour"),
            func.sum(SessionLog.input_tokens + SessionLog.output_tokens).label("tokens"),
        ).group_by("hour").order_by(
            func.sum(SessionLog.input_tokens + SessionLog.output_tokens).desc()
        ).first()
    except Exception:
        by_hour = None

    return {
        "total_input_tokens":  total.total_input  or 0,
        "total_output_tokens": total.total_output or 0,
        "total_cost_usd":      round(total.total_cost or 0, 6),
        "total_sessions":      total.total_sessions or 0,
        "by_platform": [
            {"platform": r.platform, "cost_usd": round(r.cost, 6), "sessions": r.sessions}
            for r in by_platform
        ],
        "by_account": [
            {
                "account":  r.account or "unknown",
                "cost_usd": round(r.cost, 6),
                "sessions": r.sessions,
            }
            for r in by_account
        ],
        "by_model": [
            {"model": r.model, "tokens": r.tokens, "cost_usd": round(r.cost, 6)}
            for r in by_model
        ],
        "peak_hour": int(by_hour.hour) if by_hour else None,
    }
