from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    username: str
    display_name: str


class AlertIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    keywords: list[str] = Field(min_length=1, max_length=15)
    location: str = Field(default="", max_length=80)
    contract_type: Literal["", "cdi", "cdd", "stage", "alternance"] = ""
    zone: Literal["fr", "europe", "north_america", "latam", "apac", "africa", "world"] = "fr"
    sources: list[str] | None = None
    is_active: bool = True


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    keywords: list[str]
    location: str
    contract_type: str
    zone: str
    sources: list[str] | None
    is_active: bool
    last_refreshed_at: datetime | None
    job_count: int = 0
    favorite_count: int = 0


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: str
    location: str
    url: str
    source: str
    score: float
    contract_type: str
    published_at: datetime | None
    fetched_at: datetime
    is_favorite: bool
    is_hidden: bool


class ChatAttachment(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    media_type: Literal["application/pdf", "text/plain"]
    data: str = Field(min_length=1, max_length=15_000_000)  # base64, ~11 Mo de fichier max


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)
    attachment: ChatAttachment | None = None


class ChatIn(BaseModel):
    job_id: int
    messages: list[ChatMessage] = Field(min_length=1, max_length=30)
