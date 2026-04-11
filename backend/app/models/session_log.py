from sqlalchemy import Column, Integer, String, BigInteger, Float, DateTime, func
from app.core.database import Base


class SessionLog(Base):
    __tablename__ = "session_logs"

    id            = Column(Integer, primary_key=True, index=True)
    platform      = Column(String, nullable=False)
    model         = Column(String, nullable=False)
    input_tokens  = Column(BigInteger, nullable=False)
    output_tokens = Column(BigInteger, nullable=False)
    cost_usd      = Column(Float, nullable=False)
    label         = Column(String, nullable=True)
    git_branch    = Column(String, nullable=True)
    project       = Column(String, nullable=True)
    logged_at     = Column(DateTime(timezone=True), server_default=func.now())
