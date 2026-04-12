from sqlalchemy import Column, Integer, String, BigInteger, Float, DateTime, func
from src.backend.app.core.database import Base


class SessionLog(Base):
    __tablename__ = "session_logs"

    id            = Column(Integer, primary_key=True, index=True)
    platform      = Column(String, nullable=False)        # "claude" | "copilot"
    account       = Column(String, nullable=True)         # "claude-azmi" | "claude-figul" | "copilot-azmi"
    model         = Column(String, nullable=False)        # e.g. "claude-sonnet-4-6"
    input_tokens  = Column(BigInteger, nullable=False)
    output_tokens = Column(BigInteger, nullable=False)
    cost_usd      = Column(Float, nullable=False)
    label         = Column(String, nullable=True)         # task / session description
    git_branch    = Column(String, nullable=True)
    project       = Column(String, nullable=True)         # e.g. "petrochina-eproc"
    logged_at     = Column(DateTime(timezone=True), server_default=func.now())
