from routing import Category, Queue, classify_ticket, queue_for_category
import sqlite3
from contextlib import closing
from pathlib import Path
from reply_drafting import generate_reply
from fastapi import FastAPI, HTTPException, status
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, status
from pydantic import BaseModel, StringConstraints
from ai_classifier import classify_ticket_with_ai
from routing import Category, Queue, queue_for_category

app = FastAPI(title="Customer Support Ticket Automation")


class TicketRequest(BaseModel):
    subject: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ]
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
    ]


class TicketResponse(TicketRequest):
    id: UUID
    status: Literal["received", "routed", "needs_review"]
    category: Category | None = None
    queue: Queue | None = None

class ReplyApproval(BaseModel):
    final_reply: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=3000)
    ]


class TicketReply(BaseModel):
    ticket_id: UUID
    draft_reply: str
    approved_reply: str | None = None

DB_PATH = Path(__file__).with_name("tickets.db")


def initialize_database() -> None:
    
    with closing(sqlite3.connect(DB_PATH)) as connection, connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS ticket_replies (
                ticket_id TEXT PRIMARY KEY,
                draft_reply TEXT NOT NULL,
                approved_reply TEXT
            )
        """)
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(tickets)")
        }
        if "category" not in columns:
            connection.execute("ALTER TABLE tickets ADD COLUMN category TEXT")
        if "queue" not in columns:
            connection.execute("ALTER TABLE tickets ADD COLUMN queue TEXT")


initialize_database()


@app.post("/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(request: TicketRequest) -> TicketResponse:
    category = classify_ticket_with_ai(request.subject, request.message)
    queue = queue_for_category(category)

    ticket = TicketResponse(
        id=uuid4(),
        subject=request.subject,
        message=request.message,
        status="needs_review" if queue == "manual_review" else "routed",
        category=category,
        queue=queue,
    )

    with closing(sqlite3.connect(DB_PATH)) as connection, connection:
        connection.execute(
            """
            INSERT INTO tickets (id, subject, message, status, category, queue)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(ticket.id),
                ticket.subject,
                ticket.message,
                ticket.status,
                ticket.category,
                ticket.queue,
            ),
        )

    return ticket
@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: UUID) -> TicketResponse:
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        ticket = connection.execute(
            "SELECT id, subject, message, status, category, queue FROM tickets WHERE id = ?",
            (str(ticket_id),),
        ).fetchone()

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return TicketResponse.model_validate(dict(ticket))
@app.get("/tickets/{ticket_id}/draft")
def get_ticket_draft(ticket_id: UUID) -> TicketReply:
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT ticket_id, draft_reply, approved_reply
            FROM ticket_replies
            WHERE ticket_id = ?
            """,
            (str(ticket_id),),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    return TicketReply.model_validate(dict(row))


@app.post("/tickets/{ticket_id}/draft", status_code=status.HTTP_201_CREATED)
def create_ticket_draft(ticket_id: UUID) -> TicketReply:
    ticket = get_ticket(ticket_id)

    with closing(sqlite3.connect(DB_PATH)) as connection:
        existing_draft = connection.execute(
            "SELECT 1 FROM ticket_replies WHERE ticket_id = ?",
            (str(ticket_id),),
        ).fetchone()

    if existing_draft is not None:
        raise HTTPException(status_code=409, detail="A draft already exists")

    draft = generate_reply(ticket.subject, ticket.message)
    if draft is None:
        raise HTTPException(
            status_code=503,
            detail="Could not generate a draft. Try again later.",
        )

    with closing(sqlite3.connect(DB_PATH)) as connection, connection:
        result = connection.execute(
            """
            INSERT INTO ticket_replies (ticket_id, draft_reply)
            VALUES (?, ?)
            ON CONFLICT(ticket_id) DO NOTHING
            """,
            (str(ticket_id), draft),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="A draft already exists")

    return TicketReply(ticket_id=ticket_id, draft_reply=draft)


@app.put("/tickets/{ticket_id}/draft/approval")
def approve_ticket_draft(ticket_id: UUID, approval: ReplyApproval) -> TicketReply:
    with closing(sqlite3.connect(DB_PATH)) as connection, connection:
        result = connection.execute(
            """
            UPDATE ticket_replies
            SET approved_reply = ?
            WHERE ticket_id = ? AND approved_reply IS NULL
            """,
            (approval.final_reply, str(ticket_id)),
        )

        if result.rowcount == 0:
            reply = get_ticket_draft(ticket_id)
            if reply.approved_reply != approval.final_reply:
                raise HTTPException(status_code=409, detail="Draft already approved")
            return reply

    return get_ticket_draft(ticket_id)