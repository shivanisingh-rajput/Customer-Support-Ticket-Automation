from routing import Category, Queue, classify_ticket, queue_for_category
import sqlite3
from contextlib import closing
from pathlib import Path

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