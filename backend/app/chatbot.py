"""LandBot AI: a lightweight rule/retrieval-based natural-language assistant
over the project database. No external LLM API is required, so the chatbot
works fully offline/self-contained -- it pattern-matches the user's question
into an intent, runs the matching database query, and formats a natural
sentence, similar to the "LandBot AI" concept from the original brief.

Intents are tried in order from most to least specific; the last resort
before the generic help message is "does this message mention a place we
know about", which is what makes free-form asks like "give the projects in
chennai" or "chennai projects" work without needing exact phrasing.

Rewritten from raw sqlite3 SQL to SQLAlchemy ORM queries against PostgreSQL.
"""
import re
from collections import Counter

from sqlalchemy.orm import Session

from app import services
from app.ml.data_generator import PROJECT_TYPES
from app.models import LegalDispute, Project

GREETINGS = {"hi", "hello", "hey", "hii", "hiya", "yo", "help", "what can you do", "menu"}


def _find_project_type_in_text(text: str, types) -> str | None:
    text_lower = text.lower()
    for t in sorted(types, key=len, reverse=True):
        if t.lower() in text_lower:
            return t
    return None


def _known_locations(db: Session):
    states = {r[0] for r in db.query(Project.state).distinct().all()}
    districts = {r[0] for r in db.query(Project.district).distinct().all()}
    return states, districts


def _find_location_in_text(text: str, states: set, districts: set):
    text_lower = text.lower()
    # longer names first so e.g. "North 24 Parganas" wins over a shorter partial match
    for d in sorted(districts, key=len, reverse=True):
        if d.lower() in text_lower:
            return "district", d
    for s in sorted(states, key=len, reverse=True):
        if s.lower() in text_lower:
            return "state", s
    return None, None


def _all_projects(db: Session) -> list[dict]:
    return [services.to_dict(r) for r in db.query(Project).all()]


def _projects_in_location(db: Session, loc_type: str, loc_value: str) -> list[dict]:
    if loc_type == "state":
        return [services.to_dict(r) for r in db.query(Project).filter(Project.state == loc_value).all()]
    if loc_type == "district":
        return [services.to_dict(r) for r in db.query(Project).filter(Project.district == loc_value).all()]
    return []


def _top_n_at_risk(db: Session, n: int = 10, projects: list[dict] | None = None):
    if projects is None:
        projects = _all_projects(db)
    risk_map = services.latest_risk_map(db, [p["id"] for p in projects])
    rows = [(p, risk_map[p["id"]]) for p in projects if p["id"] in risk_map]
    rows.sort(key=lambda pr: -pr[1]["risk_score"])
    return rows[:n]


def _format_project_lines(rows: list[tuple[dict, dict]]) -> str:
    return "\n".join(
        f"{i+1}. {p['name']} ({p['district']}, {p['state']}) — {ra['risk_score']*100:.0f}% risk ({ra['risk_tier']})"
        for i, (p, ra) in enumerate(rows)
    )


def _location_summary(db: Session, loc_type: str, loc_value: str) -> dict:
    projects = _projects_in_location(db, loc_type, loc_value)
    if not projects:
        return {
            "response": f"I couldn't find any projects in \"{loc_value}\". Try naming a specific state or district.",
            "data": None,
        }

    risk_map = services.latest_risk_map(db, [p["id"] for p in projects])
    tiers = Counter(ra["risk_tier"] for ra in risk_map.values())
    rows = sorted(
        ((p, risk_map[p["id"]]) for p in projects if p["id"] in risk_map),
        key=lambda pr: -pr[1]["risk_score"],
    )[:10]

    header = (
        f"{loc_value} has {len(projects)} project(s): "
        f"{tiers.get('high', 0)} high risk, {tiers.get('medium', 0)} medium risk, {tiers.get('low', 0)} low risk."
    )
    body = _format_project_lines(rows)
    response = f"{header}\n{body}" if body else header

    return {
        "response": response,
        "data": {
            "location": loc_value, "project_count": len(projects), "risk_breakdown": dict(tiers),
            "projects": [{"project_id": p["id"], "name": p["name"], "risk_score": ra["risk_score"],
                          "risk_tier": ra["risk_tier"]} for p, ra in rows],
        },
    }


def _compensation_summary(db: Session, projects: list[dict] | None, label: str) -> dict:
    if projects is None:
        projects = _all_projects(db)
    if not projects:
        return {"response": f"I couldn't find any projects for {label}.", "data": None}

    total = sum(p["compensation_total_inr"] for p in projects)
    disbursed = sum(p["compensation_disbursed_inr"] for p in projects)
    pending = total - disbursed
    pct = round(disbursed / total * 100, 1) if total else 0.0

    def fmt_inr(v: float) -> str:
        if v >= 1e7:
            return f"₹{v/1e7:.1f} Cr"
        if v >= 1e5:
            return f"₹{v/1e5:.1f} L"
        return f"₹{v:,.0f}"

    response = (
        f"Across {len(projects)} project(s) in {label}, {fmt_inr(pending)} in compensation is still pending "
        f"({pct:.0f}% of {fmt_inr(total)} total has been disbursed so far)."
    )
    return {"response": response, "data": {"total_inr": total, "disbursed_inr": disbursed, "pending_inr": pending}}


def _legal_disputes_summary(db: Session, projects: list[dict] | None, label: str) -> dict:
    if projects is None:
        projects = _all_projects(db)
    project_ids = [p["id"] for p in projects]
    if not project_ids:
        return {"response": f"I couldn't find any projects for {label}.", "data": None}

    disputes = [
        services.to_dict(r)
        for r in db.query(LegalDispute)
        .filter(LegalDispute.status == "active", LegalDispute.project_id.in_(project_ids))
        .all()
    ]
    if not disputes:
        return {"response": f"No active legal disputes in {label} right now.", "data": {"active_disputes": 0}}

    by_project = Counter(d["project_id"] for d in disputes)
    projects_by_id = {p["id"]: p for p in projects}
    top = by_project.most_common(5)
    lines = [f"- {projects_by_id[pid]['name']}: {count} active case(s)" for pid, count in top]
    response = f"{len(disputes)} active legal dispute(s) across {len(by_project)} project(s) in {label}:\n" + "\n".join(lines)
    return {"response": response, "data": {"active_disputes": len(disputes), "projects_affected": len(by_project)}}


def _delayed_projects_summary(db: Session, projects: list[dict] | None, label: str) -> dict:
    if projects is None:
        projects = _all_projects(db)
    delayed = [p for p in projects if p["status"] == "delayed"]
    if not delayed:
        return {"response": f"No projects are currently past their deadline in {label}.", "data": {"delayed_count": 0}}

    lines = [
        f"{i+1}. {p['name']} ({p['district']}, {p['state']}) — deadline was {p['deadline']}"
        for i, p in enumerate(delayed[:10])
    ]
    response = f"{len(delayed)} project(s) are already past their deadline in {label}:\n" + "\n".join(lines)
    return {"response": response, "data": {"delayed_count": len(delayed)}}


def _project_lookup(db: Session, text: str) -> dict | None:
    project = db.query(Project).filter(Project.name.ilike(f"%{text}%")).first()
    if not project:
        # try matching on individual significant words (e.g. "muzaffarpur metro" or just "metro")
        words = [w for w in re.findall(r"[a-zA-Z]{4,}", text) if w.lower() not in
                 {"project", "projects", "risk", "about", "show", "give", "tell", "what", "details"}]
        for w in words:
            project = db.query(Project).filter(Project.name.ilike(f"%{w}%")).first()
            if project:
                break
    if not project:
        return None

    project = services.to_dict(project)
    ra = services.get_latest_risk(db, project["id"])
    if not ra:
        return None
    return {
        "response": (
            f"{project['name']} ({project['district']}, {project['state']}) has a risk score of "
            f"{ra['risk_score']*100:.0f}% ({ra['risk_tier'].title()} risk), predicted delay "
            f"{ra['predicted_delay_days']:.0f} days. "
            f"Top factor: {ra['top_factors'][0]['factor'] if ra['top_factors'] else 'n/a'}. "
            f"Recommended: {ra['recommendations'][0] if ra['recommendations'] else 'n/a'}"
        ),
        "data": {"project_id": project["id"], "risk_score": ra["risk_score"], "risk_tier": ra["risk_tier"]},
    }


def answer(db: Session, message: str) -> dict:
    text = message.strip()
    lower = text.lower()
    states, districts = _known_locations(db)
    loc_type, loc_value = _find_location_in_text(text, states, districts)
    location_label = loc_value or "all tracked projects"
    location_projects = _projects_in_location(db, loc_type, loc_value) if loc_type else None

    # Greeting / help
    if lower in GREETINGS or len(lower) <= 3:
        return {
            "response": (
                "Hi, I'm LandBot AI 🤖. Ask me things like: \"top 10 projects at risk\", "
                "\"projects in Chennai\", \"why are projects in Bihar delayed\", "
                "\"compensation pending in Telangana\", \"active legal disputes\", "
                "\"which projects are delayed\", or \"which department is the bottleneck\"."
            ),
            "data": None,
        }

    # What-if / simulator questions -> point them to the right screen (checked
    # early since "what if we resolve legal disputes" would otherwise also
    # match the "legal" keyword intent below)
    if "what if" in lower or "simulate" in lower or "simulator" in lower:
        return {
            "response": (
                "Open a project's detail page and click \"What-If Simulator\" — you can toggle resolving "
                "legal disputes, releasing compensation, or clearing approvals, and I'll show the predicted "
                "risk change live."
            ),
            "data": None,
        }

    # Top N at-risk (optionally scoped to a location)
    m = re.search(r"top\s+(\d+)", lower)
    if (
        "at risk" in lower
        or ("top" in lower and "risk" in lower)
        or "most at risk" in lower
        or "most risk" in lower
        or "riskiest" in lower
        or "highest risk" in lower
    ):
        n = int(m.group(1)) if m else 10
        rows = _top_n_at_risk(db, n, projects=location_projects)
        lines = _format_project_lines(rows)
        scope = f" in {loc_value}" if loc_value else ""
        return {
            "response": (f"Top {len(rows)} projects at risk{scope}:\n" + lines) if lines else f"No project risk data available for {location_label}.",
            "data": [{"project_id": p["id"], "name": p["name"], "risk_score": ra["risk_score"], "risk_tier": ra["risk_tier"]}
                     for p, ra in rows],
        }

    # Why are projects delayed (optionally scoped to a location)
    if "why" in lower and ("delay" in lower or "risk" in lower or "stuck" in lower):
        projects = location_projects if loc_type else _all_projects(db)
        if not projects:
            return {"response": f"I couldn't find any projects for {location_label}.", "data": None}
        risk_map = services.latest_risk_map(db, [p["id"] for p in projects])
        factor_counter = Counter()
        for p in projects:
            ra = risk_map.get(p["id"])
            if ra and ra["top_factors"]:
                top = ra["top_factors"][0]
                if top.get("direction") == "increases":
                    factor_counter[top["factor"]] += 1
        if factor_counter:
            top_reasons = ", ".join(f"{factor} ({count} project(s))" for factor, count in factor_counter.most_common(3))
            resp = f"In {location_label}, the major contributing factors are: {top_reasons}."
        else:
            resp = f"I don't have enough risk data yet for {location_label}."
        return {"response": resp, "data": {"location": location_label, "project_count": len(projects)}}

    # Dashboard-style tier counts (optionally scoped to a location)
    if "how many" in lower and ("high risk" in lower or "medium risk" in lower or "low risk" in lower or "project" in lower or "delay" in lower):
        projects = location_projects if loc_type else None
        risk_map = services.latest_risk_map(db, [p["id"] for p in projects] if projects else None)
        tiers = Counter(ra["risk_tier"] for ra in risk_map.values())
        scope = f" in {loc_value}" if loc_value else ""
        return {
            "response": (
                f"There are currently {tiers.get('high', 0)} high-risk, {tiers.get('medium', 0)} medium-risk, "
                f"and {tiers.get('low', 0)} low-risk project(s){scope}."
            ),
            "data": dict(tiers),
        }

    # Bottleneck / department causing delays (optionally scoped to a location)
    if "department" in lower or "bottleneck" in lower:
        if loc_type and location_projects:
            ids = [p["id"] for p in location_projects]
            approvals = services.get_approvals_for_projects(db, ids)
        else:
            approvals = services.get_all_approvals(db)
        report = services.build_bottleneck_report(approvals, project_id=None)
        return {"response": report["narrative"], "data": report}

    # Compensation pending
    if "compensation" in lower:
        return _compensation_summary(db, location_projects, location_label)

    # Legal disputes / court cases
    if "legal" in lower or "dispute" in lower or "court case" in lower:
        return _legal_disputes_summary(db, location_projects, location_label)

    # Delayed / overdue projects
    if "delayed" in lower or "overdue" in lower or "past deadline" in lower or "behind schedule" in lower:
        return _delayed_projects_summary(db, location_projects, location_label)

    # General "projects in <location>" catch-all — this is what makes free-form
    # asks like "give the projects in chennai" work without exact phrasing.
    # If a project type is also named (e.g. "the Metro Rail project in
    # Muzaffarpur"), narrow to that type first so a single clear match
    # returns full project detail instead of a generic list.
    if loc_type:
        project_type_hint = _find_project_type_in_text(text, PROJECT_TYPES)
        if project_type_hint and location_projects:
            narrowed = [p for p in location_projects if p["project_type"] == project_type_hint]
            if len(narrowed) == 1:
                result = _project_lookup(db, narrowed[0]["name"])
                if result:
                    return result
            elif narrowed:
                rows = _top_n_at_risk(db, len(narrowed), projects=narrowed)
                lines = _format_project_lines(rows)
                return {
                    "response": f"{project_type_hint} projects in {loc_value}:\n{lines}",
                    "data": [{"project_id": p["id"], "name": p["name"], "risk_score": ra["risk_score"],
                              "risk_tier": ra["risk_tier"]} for p, ra in rows],
                }
        return _location_summary(db, loc_type, loc_value)

    # Specific project name lookup
    project_result = _project_lookup(db, text)
    if project_result:
        return project_result

    return {
        "response": (
            "I can help with questions like: \"show me the top 10 projects at risk\", "
            "\"projects in Chennai\", \"why are projects in Telangana facing delays\", "
            "\"compensation pending in Bihar\", \"active legal disputes\", "
            "\"which projects are delayed\", \"how many high risk projects are there\", "
            "or \"which department is the bottleneck\"."
        ),
        "data": None,
    }
