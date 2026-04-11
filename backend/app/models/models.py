from sqlalchemy import Column, Integer, String, BigInteger, Float, DateTime, func
from database import Base

class SessionLog(Base):
    __tablename__ = "session_logs"

    id            = Column(Integer, primary_key=True, index=True)
    platform      = Column(String, nullable=False)        # "claude" | "copilot"
    model         = Column(String, nullable=False)        # e.g. "claude-sonnet-4-6"
    input_tokens  = Column(BigInteger, nullable=False)
    output_tokens = Column(BigInteger, nullable=False)
    cost_usd      = Column(Float, nullable=False)
    label         = Column(String, nullable=True)         # nama task / project
    git_branch    = Column(String, nullable=True)         # branch saat session
    project       = Column(String, nullable=True)         # e.g. "petrochina-eproc"
    logged_at     = Column(DateTime(timezone=True), server_default=func.now())
