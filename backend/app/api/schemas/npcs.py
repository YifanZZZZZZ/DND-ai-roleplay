from datetime import datetime

from pydantic import Field

from backend.app.api.schemas.base import ApiSchema


class NpcCreate(ApiSchema):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="", max_length=400)
    personality: str = Field(default="", max_length=800)
    ideal: str = Field(default="", max_length=400)
    bond: str = Field(default="", max_length=400)
    flaw: str = Field(default="", max_length=400)
    knows: str = Field(default="", max_length=1200)
    wants: str = Field(default="", max_length=600)
    voice: str = Field(default="", max_length=600)


class NpcUpdate(ApiSchema):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: str | None = Field(default=None, max_length=400)
    personality: str | None = Field(default=None, max_length=800)
    ideal: str | None = Field(default=None, max_length=400)
    bond: str | None = Field(default=None, max_length=400)
    flaw: str | None = Field(default=None, max_length=400)
    knows: str | None = Field(default=None, max_length=1200)
    wants: str | None = Field(default=None, max_length=600)
    voice: str | None = Field(default=None, max_length=600)


class NpcView(ApiSchema):
    id: str
    campaign_id: str
    name: str
    role: str
    personality: str
    ideal: str
    bond: str
    flaw: str
    knows: str
    wants: str
    voice: str
    source: str
    revision: int
    created_at: datetime
    updated_at: datetime
