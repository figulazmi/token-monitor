from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SessionLogCreate(BaseModel):
    platform:      str
    account:       Optional[str] = None   # "claude-azmi" | "claude-figur" | "copilot-azmi"
    model:         str
    input_tokens:  int
    output_tokens: int
    label:         Optional[str] = None
    git_branch:    Optional[str] = None
    project:       Optional[str] = None


class SessionLogResponse(BaseModel):
    id:            int
    platform:      str
    account:       Optional[str]
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
    total_input_tokens:  int
    total_output_tokens: int
    total_cost_usd:      float
    total_sessions:      int
    by_platform:         list[dict]
    by_account:          list[dict]
    by_model:            list[dict]
    peak_hour:           Optional[int]
