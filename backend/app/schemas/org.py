from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict


class OrgBase(BaseModel):
    name: str
    slug: str


class OrgCreate(BaseModel):
    name: str
    slug: str


class OrgResponse(OrgBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
