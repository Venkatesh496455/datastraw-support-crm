"""
Datastraw Assessment - Customer Support Ticketing CRM
Full-stack app: FastAPI + SQLite + server-rendered HTML/Tailwind + vanilla JS.

Stand-out feature: Priority triage.
Real support teams handling hundreds of tickets/day across channels need to
know what to work on FIRST, not just what's oldest. Tickets get a priority
(Low/Normal/High/Urgent) at creation, the list is sortable/filterable by it,
and any Open/In Progress ticket sitting for 2+ days is visually flagged as
stale. Tradeoff: no real SLA timers, emails, or auto-escalation - just a
lightweight signal, because a full SLA engine was out of scope for a 2-3 day
build and would add complexity without a clear payoff at this stage.
"""
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import get_db, init_db
from app.schemas import (
    TicketCreate,
    TicketCreateResponse,
    TicketListItem,
    TicketDetail,
    TicketUpdate,
    TicketUpdateResponse,
    NoteOut,
    PrioritySuggestRequest,
    PrioritySuggestResponse,
)

# --- Hugging Face AI-assisted priority suggestion --------------------------
# Uses a free zero-shot classification model via HF's Inference API.
# This only SUGGESTS a priority - the agent creating the ticket always
# confirms/overrides it in the dropdown. If the HF call fails or times out,
# we fail soft and return "Normal" so ticket creation is never blocked by
# a third-party API being down.
HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")
HF_MODEL_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"
PRIORITY_LABELS = ["low priority", "normal priority", "high priority", "urgent priority"]
LABEL_TO_PRIORITY = {
    "low priority": "Low",
    "normal priority": "Normal",
    "high priority": "High",
    "urgent priority": "Urgent",
}


def suggest_priority_from_text(subject: str, description: str) -> tuple[str, float]:
    """Returns (priority, confidence). Falls back to ('Normal', 0.0) on any failure."""
    if not HF_API_TOKEN:
        return "Normal", 0.0

    text = f"{subject}. {description}"[:1000]
    try:
        resp = requests.post(
            HF_MODEL_URL,
            headers={"Authorization": f"Bearer {HF_API_TOKEN}"},
            json={"inputs": text, "parameters": {"candidate_labels": PRIORITY_LABELS}},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        top_label = data["labels"][0]
        top_score = data["scores"][0]
        return LABEL_TO_PRIORITY.get(top_label, "Normal"), round(top_score, 2)
    except Exception:
        # Model cold-start, rate limit, network issue, etc. - never break ticket creation.
        return "Normal", 0.0

BASE_DIR = Path(__file__).parent
VALID_STATUSES = {"Open", "In Progress", "Closed"}
VALID_PRIORITIES = {"Low", "Normal", "High", "Urgent"}

app = FastAPI(title="Datastraw Support CRM")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def generate_ticket_id(conn) -> str:
    """TKT-001, TKT-002, ... based on current row count. Falls back to a
    short uuid suffix on the rare chance of a collision."""
    cur = conn.execute("SELECT COUNT(*) as c FROM tickets")
    n = cur.fetchone()["c"] + 1
    candidate = f"TKT-{n:03d}"
    exists = conn.execute(
        "SELECT 1 FROM tickets WHERE ticket_id = ?", (candidate,)
    ).fetchone()
    if exists:
        candidate = f"TKT-{n:03d}-{uuid.uuid4().hex[:4]}"
    return candidate


# ---------------------------------------------------------------------------
# API ENDPOINTS
# ---------------------------------------------------------------------------

@app.post("/api/tickets", response_model=TicketCreateResponse)
def create_ticket(payload: TicketCreate):
    if payload.priority not in VALID_PRIORITIES:
        raise HTTPException(400, f"priority must be one of {sorted(VALID_PRIORITIES)}")

    ts = now_iso()
    with get_db() as conn:
        ticket_id = generate_ticket_id(conn)
        conn.execute(
            """INSERT INTO tickets
               (ticket_id, customer_name, customer_email, subject, description,
                status, priority, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'Open', ?, ?, ?)""",
            (
                ticket_id,
                payload.customer_name.strip(),
                str(payload.customer_email),
                payload.subject.strip(),
                payload.description.strip(),
                payload.priority,
                ts,
                ts,
            ),
        )
    return TicketCreateResponse(ticket_id=ticket_id, created_at=ts)


@app.post("/api/tickets/suggest-priority", response_model=PrioritySuggestResponse)
def suggest_priority(payload: PrioritySuggestRequest):
    """AI-assisted priority suggestion (Hugging Face zero-shot classification).
    Suggestion only - the agent always confirms the final priority."""
    priority, confidence = suggest_priority_from_text(payload.subject, payload.description)
    return PrioritySuggestResponse(suggested_priority=priority, confidence=confidence)


@app.get("/api/tickets", response_model=list[TicketListItem])
def list_tickets(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    sort: str = Query(default="newest"),  # newest | oldest | priority
):
    if status and status not in VALID_STATUSES:
        raise HTTPException(400, f"status must be one of {sorted(VALID_STATUSES)}")
    if priority and priority not in VALID_PRIORITIES:
        raise HTTPException(400, f"priority must be one of {sorted(VALID_PRIORITIES)}")

    query = "SELECT ticket_id, customer_name, subject, status, priority, created_at FROM tickets WHERE 1=1"
    params: list = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    if search:
        query += """ AND (
            customer_name LIKE ? OR
            customer_email LIKE ? OR
            ticket_id LIKE ? OR
            subject LIKE ? OR
            description LIKE ?
        )"""
        like = f"%{search.strip()}%"
        params.extend([like, like, like, like, like])

    if sort == "oldest":
        query += " ORDER BY created_at ASC"
    elif sort == "priority":
        # Urgent > High > Normal > Low
        query += """ ORDER BY
            CASE priority
                WHEN 'Urgent' THEN 0
                WHEN 'High' THEN 1
                WHEN 'Normal' THEN 2
                WHEN 'Low' THEN 3
                ELSE 4
            END, created_at DESC"""
    else:
        query += " ORDER BY created_at DESC"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [TicketListItem(**dict(r)) for r in rows]


@app.get("/api/tickets/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Ticket not found")

        notes = conn.execute(
            "SELECT note_text, created_at FROM notes WHERE ticket_id = ? ORDER BY created_at ASC",
            (ticket_id,),
        ).fetchall()

    return TicketDetail(
        ticket_id=row["ticket_id"],
        customer_name=row["customer_name"],
        customer_email=row["customer_email"],
        subject=row["subject"],
        description=row["description"],
        status=row["status"],
        priority=row["priority"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        notes=[NoteOut(note_text=n["note_text"], created_at=n["created_at"]) for n in notes],
    )


@app.put("/api/tickets/{ticket_id}", response_model=TicketUpdateResponse)
def update_ticket(ticket_id: str, payload: TicketUpdate):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Ticket not found")

        if payload.status is not None:
            if payload.status not in VALID_STATUSES:
                raise HTTPException(400, f"status must be one of {sorted(VALID_STATUSES)}")

        ts = now_iso()

        if payload.status is not None:
            conn.execute(
                "UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
                (payload.status, ts, ticket_id),
            )
        else:
            conn.execute(
                "UPDATE tickets SET updated_at = ? WHERE ticket_id = ?",
                (ts, ticket_id),
            )

        if payload.notes:
            conn.execute(
                "INSERT INTO notes (ticket_id, note_text, created_at) VALUES (?, ?, ?)",
                (ticket_id, payload.notes.strip(), ts),
            )

    return TicketUpdateResponse(success=True, updated_at=ts)


# ---------------------------------------------------------------------------
# FRONTEND (served as static files)
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
def serve_home():
    return FileResponse(BASE_DIR / "templates" / "index.html")


@app.get("/ticket/{ticket_id}")
def serve_detail(ticket_id: str):
    return FileResponse(BASE_DIR / "templates" / "detail.html")


@app.get("/new")
def serve_new():
    return FileResponse(BASE_DIR / "templates" / "new.html")
