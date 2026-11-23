import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, status
from pydantic import BaseModel, StringConstraints


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
    status: Literal["received"]


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


initialize_database()


@app.post("/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(request: TicketRequest) -> TicketResponse:
    ticket = TicketResponse(
        id=uuid4(),
        subject=request.subject,
        message=request.message,
        status="received",
    )
    with closing(sqlite3.connect(DB_PATH)) as connection, connection:
        connection.execute(
            "INSERT INTO tickets (id, subject, message, status) VALUES (?, ?, ?, ?)",
            (str(ticket.id), ticket.subject, ticket.message, ticket.status),
        )
    return ticket
@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: UUID) -> TicketResponse:
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        ticket = connection.execute(
            "SELECT id, subject, message, status FROM tickets WHERE id = ?",
            (str(ticket_id),),
        ).fetchone()

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return TicketResponse.model_validate(dict(ticket))