from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SessionLogCreate(BaseModel):
    """Shape data yang diterima dari request POST /log"""
    platform:      str
    model:         str
    input_tokens:  int
    output_tokens: int
    label:         Optional[str] = None
    git_branch:    Optional[str] = None
    project:       Optional[str] = None


class SessionLogResponse(BaseModel):
    """Shape data yang dikembalikan ke client"""
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

    model_config = {"from_attributes": True}


class StatsResponse(BaseModel):
    """Shape response GET /stats"""
    total_input_tokens:  int
    total_output_tokens: int
    total_cost_usd:      float
    total_sessions:      int
    by_platform:         list[dict]
    by_model:            list[dict]
    peak_hour:           Optional[int]
