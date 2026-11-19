from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from ..auth import current_user
from ..db import get_db
from ..models import Comment, Label, Status, Ticket, User
from ..schemas import CommentIn, LabelOut, TicketIn, TicketOut

router = APIRouter()
def ticket_query(): return select(Ticket).options(joinedload(Ticket.created_by), joinedload(Ticket.assigned_to), joinedload(Ticket.closed_by), joinedload(Ticket.labels), joinedload(Ticket.comments).joinedload(Comment.author))
@router.get("/labels", response_model=list[LabelOut])
def available_labels(db: Session = Depends(get_db), user: User = Depends(current_user)): return db.scalars(select(Label).order_by(Label.name)).all()
@router.get("", response_model=list[TicketOut])
def list_tickets(status: Status | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = ticket_query().order_by(Ticket.created_at.desc())
    if status: q = q.where(Ticket.status == status)
    return db.scalars(q).unique().all()
@router.post("", response_model=TicketOut)
def create_ticket(data: TicketIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    labels = list(db.scalars(select(Label).where(Label.id.in_(data.label_ids)))) if data.label_ids else []
    ticket = Ticket(title=data.title, description=data.description, created_by_id=user.id, labels=labels)
    db.add(ticket); db.commit(); db.refresh(ticket); return db.scalars(ticket_query().where(Ticket.id == ticket.id)).unique().one()
@router.post("/{ticket_id}/assign", response_model=TicketOut)
def assign(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    ticket = db.get(Ticket, ticket_id)
    if not ticket: raise HTTPException(404, "Ticket not found")
    ticket.assigned_to_id = user.id; db.commit(); return db.scalars(ticket_query().where(Ticket.id == ticket_id)).unique().one()
@router.post("/{ticket_id}/complete", response_model=TicketOut)
def complete(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    ticket = db.get(Ticket, ticket_id)
    if not ticket: raise HTTPException(404, "Ticket not found")
    if ticket.assigned_to_id not in (None, user.id) and user.role.value != "admin": raise HTTPException(403, "Only the assignee can complete this ticket")
    ticket.status = Status.closed; ticket.closed_by_id = user.id; ticket.closed_at = datetime.now(timezone.utc); db.commit(); return db.scalars(ticket_query().where(Ticket.id == ticket_id)).unique().one()
@router.post("/{ticket_id}/comments", response_model=TicketOut)
def comment(ticket_id: int, data: CommentIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.get(Ticket, ticket_id): raise HTTPException(404, "Ticket not found")
    db.add(Comment(ticket_id=ticket_id, author_id=user.id, body=data.body)); db.commit(); return db.scalars(ticket_query().where(Ticket.id == ticket_id)).unique().one()
