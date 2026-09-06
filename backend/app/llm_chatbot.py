"""LandBot AI, upgraded: a real hosted LLM (via Groq's OpenAI-compatible API)
answers questions about the application using function-calling against the
live database, instead of the fixed intent list in app/chatbot.py.

How it works
------------
1. The user's message is sent to the model along with a set of "tools" --
   plain functions like search_projects / get_project_detail /
   get_compensation_summary / get_bottleneck_report / get_dashboard_summary
   / get_legal_disputes_summary / get_alerts / list_known_filters.
2. The model decides which tool(s) to call and with what arguments (it can
   call more than one, and can chain calls across a few turns -- e.g. look up
   valid district names first, then search with the corrected spelling).
3. We execute the requested tool(s) against the real SQLite database and
   feed the JSON result back to the model.
4. The model writes the final natural-language answer grounded in that real
   data.

This means the bot can answer genuinely arbitrary phrasings ("give the
projects in chennai with high risk", "which state has the most legal
disputes", "how much compensation is still owed in Bihar") without needing a
hand-written intent for each one.

Requires GROQ_API_KEY (see app/config.py). If it isn't set, or if the API
call fails for any reason (no internet, bad key, rate limit, timeout), the
caller (app/routes/chatbot_routes.py) falls back to the offline rule-based
chatbot in app/chatbot.py automatically.

Uses only the Python standard library (urllib) for the HTTP call -- no new
pip dependency is required. Tool implementations below were rewritten from
raw sqlite3 SQL to SQLAlchemy ORM queries against PostgreSQL.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app import services
from app.models import Alert, LegalDispute, Project

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
MAX_TOOL_ROUNDS = 4
REQUEST_TIMEOUT_SECONDS = 25

SYSTEM_PROMPT = """You are LandBot AI, the assistant embedded in LandGuard AI -- a
predictive-analytics dashboard that tracks Indian infrastructure land-acquisition
projects (highways, metro rail, irrigation, power lines, etc.) and predicts which
ones are at risk of delay.

You answer questions about the projects, risk scores, compensation, legal
disputes, approvals/bottlenecks, and alerts tracked in the application's own
database. You have tools to query that database live -- ALWAYS call a tool to
get real data before answering any question about specific projects, numbers,
locations, or statistics. Never invent project names, numbers, or statistics.

Guidelines:
- Locations: users may type a state or district name loosely (abbreviations,
  partial names, different casing). If a location-based lookup returns nothing,
  call list_known_filters to see the real state/district names in the database
  and retry with the closest match, rather than telling the user nothing exists.
- Risk tiers are exactly "low", "medium", or "high". Project status is exactly
  "active" or "delayed".
- If a question combines multiple conditions (e.g. "high risk projects in
  Chennai", "delayed projects in Bihar with active legal disputes"), pass all
  the relevant filters to search_projects in one call rather than guessing.
- If a project name is ambiguous or not found, get_project_detail returns
  close-name suggestions -- use them to retry, or ask the user to clarify.
- For "what if" / simulator questions, don't try to compute a simulation
  yourself -- tell the user to open the project's detail page and use the
  What-If Simulator there.
- Keep answers concise and concrete: lead with the direct answer/numbers, then
  at most a couple of supporting details. Use plain text (this is a chat
  widget, not a document) -- short lines or a simple "- " list are fine,
  avoid heavy markdown.
- If the question is unrelated to this application (e.g. general chit-chat,
  topics with no connection to land-acquisition projects), politely say you
  can only help with questions about LandGuard AI's project data, and give one
  or two examples of what you can answer.
"""

# ---------------------------------------------------------------------------
# Tool implementations -- each takes the SQLAlchemy Session first, then
# keyword args parsed from the model's tool-call JSON. Return values must be
# JSON-serializable (plain dicts/lists/numbers/strings).
# ---------------------------------------------------------------------------


def _project_risk_row(db, p: dict, risk_map: dict) -> dict | None:
    ra = risk_map.get(p["id"])
    if not ra:
        return None
    return {
        "project_id": p["id"],
        "name": p["name"],
        "project_type": p["project_type"],
        "state": p["state"],
        "district": p["district"],
        "status": p["status"],
        "deadline": p["deadline"],
        "risk_score_pct": round(ra["risk_score"] * 100, 1),
        "risk_tier": ra["risk_tier"],
        "predicted_delay_days": ra["predicted_delay_days"],
    }


def tool_search_projects(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    project_type: str | None = None,
    status: str | None = None,
    risk_tier: str | None = None,
    has_active_legal_dispute: bool | None = None,
    limit: int = 15,
) -> dict:
    """Find projects matching any combination of filters, sorted by risk
    score (highest first). All filters are optional and case-insensitive
    partial matches (except status/risk_tier, which are exact)."""
    query = db.query(Project)
    if state:
        query = query.filter(Project.state.ilike(f"%{state}%"))
    if district:
        query = query.filter(Project.district.ilike(f"%{district}%"))
    if project_type:
        query = query.filter(Project.project_type.ilike(f"%{project_type}%"))
    if status:
        query = query.filter(Project.status == status.strip().lower())

    rows = [services.to_dict(r) for r in query.all()]

    if has_active_legal_dispute is not None and rows:
        ids = [p["id"] for p in rows]
        active_ids = {
            r[0]
            for r in db.query(LegalDispute.project_id)
            .filter(LegalDispute.status == "active", LegalDispute.project_id.in_(ids))
            .distinct()
            .all()
        }
        rows = [p for p in rows if (p["id"] in active_ids) == bool(has_active_legal_dispute)]

    risk_map = services.latest_risk_map(db, [p["id"] for p in rows])
    results = []
    for p in rows:
        if risk_tier and risk_map.get(p["id"], {}).get("risk_tier") != risk_tier.strip().lower():
            continue
        row = _project_risk_row(db, p, risk_map)
        if row:
            results.append(row)

    results.sort(key=lambda r: -r["risk_score_pct"])
    return {"total_matches": len(results), "projects": results[:limit]}


def tool_get_project_detail(db: Session, project_name: str | None = None, project_id: int | None = None) -> dict:
    """Full detail for one specific project: risk score, top risk factors,
    recommendations, forecast, approvals, and legal disputes. If
    project_name doesn't match anything exactly, returns close suggestions
    instead."""
    row = None
    if project_id:
        row = db.query(Project).filter(Project.id == project_id).first()
    if not row and project_name:
        row = db.query(Project).filter(Project.name.ilike(f"%{project_name}%")).first()

    if not row:
        suggestions = []
        if project_name:
            words = [w for w in project_name.split() if len(w) >= 4]
            for w in words:
                for r in db.query(Project.name).filter(Project.name.ilike(f"%{w}%")).limit(5).all():
                    if r[0] not in suggestions:
                        suggestions.append(r[0])
        return {"found": False, "message": "No project matched that name.", "suggestions": suggestions[:8]}

    project = services.derive_project_fields(
        row, services.get_approvals(db, row.id), services.get_disputes(db, row.id)
    )
    ra = services.get_latest_risk(db, row.id)
    return {
        "found": True,
        "project": {
            "project_id": project["id"],
            "name": project["name"],
            "project_type": project["project_type"],
            "state": project["state"],
            "district": project["district"],
            "status": project["status"],
            "start_date": project["start_date"],
            "deadline": project["deadline"],
            "land_area_hectares": project["land_area_hectares"],
            "affected_families": project["affected_families"],
            "compensation_total_inr": project["compensation_total_inr"],
            "compensation_disbursed_inr": project["compensation_disbursed_inr"],
            "compensation_pct_disbursed": round(project["compensation_pct_disbursed"] * 100, 1),
            "active_legal_disputes": project["active_legal_disputes"],
            "pending_approvals": project["pending_approvals"],
            "max_approval_days_pending": project["max_approval_days_pending"],
        },
        "risk": None
        if not ra
        else {
            "risk_score_pct": round(ra["risk_score"] * 100, 1),
            "risk_tier": ra["risk_tier"],
            "predicted_delay_days": ra["predicted_delay_days"],
            "top_factors": ra["top_factors"],
            "recommendations": ra["recommendations"],
            "forecast_30_60_90": ra["forecast_30_60_90"],
        },
    }


def _project_ids_for_filter(db: Session, state: str | None, district: str | None) -> list[int]:
    query = db.query(Project.id)
    if state:
        query = query.filter(Project.state.ilike(f"%{state}%"))
    if district:
        query = query.filter(Project.district.ilike(f"%{district}%"))
    return [r[0] for r in query.all()]


def tool_get_compensation_summary(db: Session, state: str | None = None, district: str | None = None) -> dict:
    """Total / disbursed / pending compensation amounts (INR), optionally
    scoped to a state or district."""
    ids = _project_ids_for_filter(db, state, district)
    if state or district:
        if not ids:
            return {"project_count": 0, "message": "No projects matched that location."}
        rows = (
            db.query(Project.compensation_total_inr, Project.compensation_disbursed_inr)
            .filter(Project.id.in_(ids))
            .all()
        )
    else:
        rows = db.query(Project.compensation_total_inr, Project.compensation_disbursed_inr).all()

    total = sum(r[0] for r in rows)
    disbursed = sum(r[1] for r in rows)
    return {
        "project_count": len(rows),
        "total_compensation_inr": round(total, 2),
        "disbursed_inr": round(disbursed, 2),
        "pending_inr": round(total - disbursed, 2),
        "pct_disbursed": round(disbursed / total * 100, 1) if total else 0.0,
    }


def tool_get_legal_disputes_summary(db: Session, state: str | None = None, district: str | None = None) -> dict:
    """Count and breakdown of ACTIVE legal disputes, optionally scoped to a
    state or district, including which projects are affected and dispute
    case types."""
    ids = _project_ids_for_filter(db, state, district)
    if state or district:
        if not ids:
            return {"active_disputes": 0, "message": "No projects matched that location."}
        rows = [
            services.to_dict(r)
            for r in db.query(LegalDispute)
            .filter(LegalDispute.status == "active", LegalDispute.project_id.in_(ids))
            .all()
        ]
    else:
        rows = [services.to_dict(r) for r in db.query(LegalDispute).filter(LegalDispute.status == "active").all()]

    if not rows:
        return {"active_disputes": 0}

    by_type: dict = {}
    by_project: dict = {}
    for d in rows:
        by_type[d["case_type"]] = by_type.get(d["case_type"], 0) + 1
        by_project[d["project_id"]] = by_project.get(d["project_id"], 0) + 1

    project_names = {}
    if by_project:
        for r in db.query(Project.id, Project.name).filter(Project.id.in_(list(by_project.keys()))).all():
            project_names[r[0]] = r[1]

    top_projects = sorted(by_project.items(), key=lambda kv: -kv[1])[:8]
    return {
        "active_disputes": len(rows),
        "projects_affected": len(by_project),
        "by_case_type": by_type,
        "top_affected_projects": [
            {"name": project_names.get(pid, f"project #{pid}"), "active_case_count": count} for pid, count in top_projects
        ],
    }


def tool_get_bottleneck_report(
    db: Session, state: str | None = None, district: str | None = None, project_name: str | None = None
) -> dict:
    """Which department (Revenue, Legal, Forest, Finance, etc.) is causing
    the most pending-approval delay -- globally, for one location, or for one
    named project."""
    project_id = None
    if project_name:
        row = db.query(Project.id).filter(Project.name.ilike(f"%{project_name}%")).first()
        if not row:
            return {"message": f"No project matched '{project_name}'."}
        project_id = row[0]
        approvals = services.get_approvals(db, project_id)
    else:
        ids = _project_ids_for_filter(db, state, district)
        if (state or district) and not ids:
            return {"message": "No projects matched that location."}
        if state or district:
            approvals = services.get_approvals_for_projects(db, ids)
        else:
            approvals = services.get_all_approvals(db)

    return services.build_bottleneck_report(approvals, project_id)


def tool_get_dashboard_summary(db: Session) -> dict:
    """Overall application stats: total projects, risk tier breakdown,
    unacknowledged critical alerts, total compensation pending, active legal
    case count."""
    projects = [services.to_dict(r) for r in db.query(Project).all()]
    risk_map = services.latest_risk_map(db)

    high = medium = low = 0
    comp_pending = 0.0
    for p in projects:
        ra = risk_map.get(p["id"])
        if ra:
            if ra["risk_tier"] == "high":
                high += 1
            elif ra["risk_tier"] == "medium":
                medium += 1
            else:
                low += 1
        comp_pending += max(0.0, p["compensation_total_inr"] - p["compensation_disbursed_inr"])

    critical_alerts = (
        db.query(func.count(Alert.id)).filter(Alert.severity == "critical", Alert.acknowledged.is_(False)).scalar()
    )
    active_legal_cases = db.query(func.count(LegalDispute.id)).filter(LegalDispute.status == "active").scalar()
    delayed_projects = sum(1 for p in projects if p["status"] == "delayed")

    return {
        "total_projects": len(projects),
        "high_risk": high,
        "medium_risk": medium,
        "low_risk": low,
        "delayed_projects": delayed_projects,
        "unacknowledged_critical_alerts": critical_alerts,
        "total_compensation_pending_inr": round(comp_pending, 2),
        "active_legal_cases": active_legal_cases,
    }


def tool_get_alerts(db: Session, severity: str | None = None, acknowledged: bool | None = None, limit: int = 10) -> dict:
    """Recent early-warning alerts (fired when a project's risk tier
    worsens), newest first."""
    query = db.query(Alert, Project.name.label("project_name")).join(Project, Project.id == Alert.project_id)
    if severity:
        query = query.filter(Alert.severity == severity.strip().lower())
    if acknowledged is not None:
        query = query.filter(Alert.acknowledged.is_(bool(acknowledged)))
    query = query.order_by(Alert.created_at.desc()).limit(max(1, min(limit, 50)))

    rows = query.all()
    return {
        "count": len(rows),
        "alerts": [
            {
                "project_name": project_name,
                "severity": alert.severity,
                "title": alert.title,
                "message": alert.message,
                "acknowledged": bool(alert.acknowledged),
                "created_at": alert.created_at,
            }
            for alert, project_name in rows
        ],
    }


def tool_list_known_filters(db: Session) -> dict:
    """The real state names, district names, project types, and status
    values that exist in the database -- use this to resolve a location or
    type the user typed loosely/incorrectly before searching."""
    return {
        "states": sorted({r[0] for r in db.query(Project.state).distinct().all()}),
        "districts": sorted({r[0] for r in db.query(Project.district).distinct().all()}),
        "project_types": sorted({r[0] for r in db.query(Project.project_type).distinct().all()}),
        "statuses": ["active", "delayed"],
        "risk_tiers": ["low", "medium", "high"],
    }


TOOL_IMPLS = {
    "search_projects": tool_search_projects,
    "get_project_detail": tool_get_project_detail,
    "get_compensation_summary": tool_get_compensation_summary,
    "get_legal_disputes_summary": tool_get_legal_disputes_summary,
    "get_bottleneck_report": tool_get_bottleneck_report,
    "get_dashboard_summary": tool_get_dashboard_summary,
    "get_alerts": tool_get_alerts,
    "list_known_filters": tool_list_known_filters,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_projects",
            "description": tool_search_projects.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {"type": "string", "description": "State name (partial/case-insensitive OK), e.g. 'Tamil Nadu'"},
                    "district": {"type": "string", "description": "District/city name (partial/case-insensitive OK), e.g. 'Chennai'"},
                    "project_type": {"type": "string", "description": "e.g. 'Metro Rail', 'Highway Expansion'"},
                    "status": {"type": "string", "enum": ["active", "delayed"]},
                    "risk_tier": {"type": "string", "enum": ["low", "medium", "high"]},
                    "has_active_legal_dispute": {"type": "boolean"},
                    "limit": {"type": "integer", "description": "Max results to return, default 15"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_detail",
            "description": tool_get_project_detail.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "Full or partial project name"},
                    "project_id": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_compensation_summary",
            "description": tool_get_compensation_summary.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {"type": "string"},
                    "district": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_legal_disputes_summary",
            "description": tool_get_legal_disputes_summary.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {"type": "string"},
                    "district": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bottleneck_report",
            "description": tool_get_bottleneck_report.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {"type": "string"},
                    "district": {"type": "string"},
                    "project_name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dashboard_summary",
            "description": tool_get_dashboard_summary.__doc__,
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_alerts",
            "description": tool_get_alerts.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["critical", "warning"]},
                    "acknowledged": {"type": "boolean"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_known_filters",
            "description": tool_list_known_filters.__doc__,
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


# ---------------------------------------------------------------------------
# Groq API plumbing
# ---------------------------------------------------------------------------


def _call_groq(messages: list[dict], use_tools: bool) -> dict:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")

    body = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": 0.3,
        "max_completion_tokens": 900,
    }
    if use_tools:
        body["tools"] = TOOL_SCHEMAS
        body["tool_choice"] = "auto"
    if settings.groq_reasoning_effort:
        body["reasoning_effort"] = settings.groq_reasoning_effort

    req = urllib.request.Request(
        GROQ_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.groq_api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Groq API returned HTTP {e.code}: {detail[:500]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach Groq API: {e.reason}") from e


def _dispatch_tool(db, name: str, raw_arguments: str | None) -> dict:
    fn = TOOL_IMPLS.get(name)
    if fn is None:
        return {"error": f"Unknown tool '{name}'"}
    try:
        args = json.loads(raw_arguments) if raw_arguments else {}
    except json.JSONDecodeError:
        args = {}
    try:
        return fn(db, **args)
    except TypeError as e:
        return {"error": f"Bad arguments for {name}: {e}"}
    except Exception as e:  # noqa: BLE001 -- surfaced to the model as a tool error, not a crash
        return {"error": f"{name} failed: {e}"}


def answer(db, message: str) -> dict:
    """Main entrypoint used by chatbot_routes.py. Raises on any failure
    (missing key, network error, bad response) so the caller can fall back
    to the offline rule-based chatbot."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]

    for round_num in range(MAX_TOOL_ROUNDS):
        allow_tools = round_num < MAX_TOOL_ROUNDS - 1
        resp = _call_groq(messages, use_tools=allow_tools)
        choices = resp.get("choices") or []
        if not choices:
            raise RuntimeError(f"Groq API returned no choices: {resp}")
        msg = choices[0]["message"]
        messages.append(msg)

        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            text = (msg.get("content") or "").strip()
            return {"response": text or "I couldn't find an answer to that from the project data.", "data": None}

        for call in tool_calls:
            fn_name = call["function"]["name"]
            result = _dispatch_tool(db, fn_name, call["function"].get("arguments"))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result, default=str)[:12000],
                }
            )

    # Exhausted rounds without a plain-text answer -- ask once more with no
    # tools available so the model is forced to summarize what it has.
    resp = _call_groq(messages, use_tools=False)
    text = (resp["choices"][0]["message"].get("content") or "").strip()
    return {"response": text or "I wasn't able to fully answer that -- could you rephrase?", "data": None}
