# Datastraw Support CRM

A full-stack customer support ticketing system built for the Datastraw
Technologies assessment. Handles ticket creation, search, filtering, status
updates, and internal notes.

**Live app:** _add your deployed URL here_
**Demo video:** _add your video link here_

## Tech Stack

- **Backend:** FastAPI (Python)
- **Database:** SQLite
- **Frontend:** Server-rendered HTML + Tailwind CSS (via CDN) + vanilla JS
- **Deployment:** Railway.app

Chosen for speed of development and zero infra overhead — SQLite needs no
separate DB server, and FastAPI's automatic request validation (via
Pydantic) keeps the API layer small and safe.

## Features

1. **Create tickets** — customer name, email, subject, description, priority
2. **List tickets** — clean table view (ID, customer, subject, priority, status, date)
3. **Live search** — across name, email, ticket ID, subject, and description
4. **Filter** — by status (Open / In Progress / Closed) and priority
5. **Ticket detail & update** — view full ticket, change status, add notes

### Stand-out feature: Priority triage

Tickets get a priority (Low / Normal / High / Urgent) at creation. The list
can be sorted by priority, and any non-closed ticket open for 2+ days is
flagged with a "stale" indicator. This mirrors how real support teams
actually triage volume — oldest-first isn't always right-first.

**Tradeoff:** no real SLA timers, escalation emails, or auto-reassignment —
just a lightweight visual signal. A full SLA engine was out of scope for a
2–3 day build and would add complexity without a clear payoff at this stage.

**AI-assisted layer:** on the new ticket form, a "Suggest with AI" button
sends the subject + description to a free Hugging Face zero-shot
classification model (`facebook/bart-large-mnli`), which suggests a
priority. The agent still confirms or overrides it before submitting — the
model informs, it doesn't decide. If the Hugging Face API is unreachable or
no token is set, the app fails soft to "Normal" rather than blocking ticket
creation. Tradeoff: zero-shot classification on short ticket text is
inherently approximate, so this is framed as a suggestion, not ground truth.

## Database Schema

```
tickets
  id              INTEGER PK
  ticket_id       TEXT UNIQUE   (e.g. TKT-001)
  customer_name   TEXT
  customer_email  TEXT
  subject         TEXT
  description     TEXT
  status          TEXT  (Open / In Progress / Closed)
  priority        TEXT  (Low / Normal / High / Urgent)
  created_at      TEXT
  updated_at      TEXT

notes
  id           INTEGER PK
  ticket_id    TEXT  (FK -> tickets.ticket_id)
  note_text    TEXT
  created_at   TEXT
```

## API Endpoints

| Method | Endpoint              | Description                          |
|--------|------------------------|---------------------------------------|
| POST   | `/api/tickets`          | Create a ticket                       |
| GET    | `/api/tickets`          | List tickets (`?status=&search=&priority=&sort=`) |
| GET    | `/api/tickets/{id}`     | Get full ticket detail + notes        |
| PUT    | `/api/tickets/{id}`     | Update status and/or add a note       |

## Running Locally

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd datastraw-crm

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the server
uvicorn app.main:app --reload

# 5. Open http://localhost:8000
```

The SQLite database (`app/crm.db`) is created automatically on first run —
no migrations needed.

## Deployment (Railway)

1. Push this repo to GitHub.
2. On [railway.app](https://railway.app), create a new project → "Deploy from GitHub repo".
3. Railway auto-detects the `Procfile` and installs from `requirements.txt`.
4. Once deployed, Railway gives you a public URL.

## Project Structure

```
datastraw-crm/
├── app/
│   ├── main.py          # FastAPI app + API routes
│   ├── database.py      # SQLite connection + schema
│   ├── schemas.py       # Pydantic request/response models
│   ├── static/
│   │   └── app.js       # Shared frontend helpers
│   └── templates/
│       ├── index.html   # Ticket list page
│       ├── new.html     # Create ticket form
│       └── detail.html  # Ticket detail + update page
├── requirements.txt
├── Procfile
├── .env.example
├── .gitignore
└── README.md
```

## Challenges & Decisions

- Chose SQLite over Postgres to keep infra minimal per the assignment's
  "don't over-engineer" guidance — trivial to swap for Postgres later via
  `DATABASE_URL` if the app needed to scale.
- Ticket IDs are generated as `TKT-XXX` sequentially, with a UUID-suffixed
  fallback to guarantee uniqueness under concurrent writes.
- Search is a simple `LIKE` query across five columns — fast enough at this
  scale; would move to a proper full-text index (e.g. Postgres `tsvector`
  or a search service) if ticket volume grew significantly.

## What I'd Improve With More Time

- Authentication for support agents (currently open access, per assignment's MVP guidance)
- Real SLA timers with escalation notifications
- Multi-channel ticket sources (email, chat, phone) as a `channel` field
- Pagination for the ticket list at high volume
