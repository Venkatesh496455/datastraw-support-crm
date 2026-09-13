from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


class TicketCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=120)
    customer_email: EmailStr
    subject: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    priority: Optional[str] = Field(default="Normal")  # Low / Normal / High / Urgent


class TicketCreateResponse(BaseModel):
    ticket_id: str
    created_at: str


class TicketListItem(BaseModel):
    ticket_id: str
    customer_name: str
    subject: str
    status: str
    priority: str
    created_at: str


class NoteOut(BaseModel):
    note_text: str
    created_at: str


class TicketDetail(BaseModel):
    ticket_id: str
    customer_name: str
    customer_email: str
    subject: str
    description: str
    status: str
    priority: str
    created_at: str
    updated_at: str
    notes: List[NoteOut] = []


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None  # new note text to append


class TicketUpdateResponse(BaseModel):
    success: bool
    updated_at: str


class PrioritySuggestRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)


class PrioritySuggestResponse(BaseModel):
    suggested_priority: str
    confidence: float  # 0.0 means the model call failed/skipped; agent should just pick manually
