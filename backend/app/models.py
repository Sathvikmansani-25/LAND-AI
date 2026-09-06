"""SQLAlchemy ORM models -- the PostgreSQL equivalent of the old sqlite3
SCHEMA string. Dates/timestamps are kept as ISO-8601 strings (not native
DATE/TIMESTAMP columns) to match exactly what the rest of the app already
produces via now_iso()/.isoformat() and expects back (services.py, the
chatbot layers, and the frontend all treat these as plain strings) -- this
keeps the FastAPI/SQLAlchemy rewrite behavior-identical to the original app
instead of silently changing wire formats.
"""
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="official")
    created_at = Column(String, nullable=False)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    project_type = Column(String, nullable=False)
    state = Column(String, nullable=False, index=True)
    district = Column(String, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    land_area_hectares = Column(Float, nullable=False)
    affected_families = Column(Integer, nullable=False)
    ownership_complexity = Column(Integer, nullable=False)
    compensation_total_inr = Column(Float, nullable=False)
    compensation_disbursed_inr = Column(Float, nullable=False)
    departments_involved = Column(Integer, nullable=False)
    start_date = Column(String, nullable=False)
    deadline = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    district_historical_delay_rate = Column(Float, nullable=False, default=0)
    created_at = Column(String, nullable=False)

    approvals = relationship("Approval", cascade="all, delete-orphan", passive_deletes=True)
    disputes = relationship("LegalDispute", cascade="all, delete-orphan", passive_deletes=True)
    risk_assessments = relationship("RiskAssessment", cascade="all, delete-orphan", passive_deletes=True)
    alerts = relationship("Alert", cascade="all, delete-orphan", passive_deletes=True)


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    department = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    days_pending = Column(Integer, nullable=False, default=0)
    requested_at = Column(String, nullable=True)
    resolved_at = Column(String, nullable=True)


class LegalDispute(Base):
    __tablename__ = "legal_disputes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    case_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    filed_at = Column(String, nullable=True)
    resolved_at = Column(String, nullable=True)


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    risk_score = Column(Float, nullable=False)
    risk_tier = Column(String, nullable=False)
    predicted_delay_days = Column(Float, nullable=False)
    # Stored as native JSON/JSONB on Postgres (SQLAlchemy's generic JSON type
    # maps to each dialect's best JSON representation, and to TEXT+manual
    # (de)serialization on SQLite for the no-setup local smoke-test path).
    top_factors = Column(JSON, nullable=False)
    recommendations = Column(JSON, nullable=False)
    forecast_30_60_90 = Column(JSON, nullable=True)
    computed_at = Column(String, nullable=False, index=True)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    severity = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    previous_tier = Column(String, nullable=True)
    new_tier = Column(String, nullable=True)
    acknowledged = Column(Boolean, nullable=False, default=False)
    created_at = Column(String, nullable=False, index=True)


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)
