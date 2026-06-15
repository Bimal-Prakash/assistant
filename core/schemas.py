from typing import Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

class CommandRequest(BaseModel):
    text: str = Field(min_length=1, description="User speech converted to text")
    client: Optional[str] = Field(default=None, description="android or pc")
    session_id: Optional[str] = Field(default=None, description="Conversation session ID for multi-turn context")

class ActionResponse(BaseModel):
    action: str
    app: Optional[str] = None
    url: Optional[str] = None
    contact: Optional[str] = None
    phone: Optional[str] = None
    text: Optional[str] = None
    message: Optional[str] = None
    response: Optional[str] = None
    level: Optional[str] = None
    type: Optional[str] = None
    state: Optional[str] = None
    target: Optional[str] = None
    
    # New agentic fields
    direction: Optional[str] = None
    shortcut: Optional[str] = None
    title: Optional[str] = None
    seconds: Optional[int] = None
    label: Optional[str] = None
    folder_path: Optional[str] = None
    query: Optional[str] = None
    contact_name: Optional[str] = None
    call_type: Optional[str] = None
