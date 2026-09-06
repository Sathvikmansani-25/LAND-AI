"""Pydantic models used to validate incoming request bodies (FastAPI applies
these automatically and returns a 422 on validation errors). Responses are
returned as plain dicts rather than typed response_models -- the shapes are
documented in README.md's API reference."""
from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class SimulationInput(BaseModel):
    resolve_legal_disputes: bool = False
    release_compensation: bool = False
    complete_pending_approvals: bool = False
    reduce_approval_days_to: Optional[int] = None


class ChatRequest(BaseModel):
    message: str
