import uuid
import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserSchema(BaseModel):
    id: uuid.UUID
    username: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class UserBaseSchema(BaseModel):
    username: Optional[str] = Field(None)
    fullname: Optional[str] = Field(None)
    email: Optional[str] = Field(None)


class UserCreateSchema(UserBaseSchema):
    password: str


class UserCreateDBSchema(UserBaseSchema):
    hashed_password: str


class TokenSchema(BaseModel):
    access_token: str
    refresh_token: uuid.UUID
    token_type: str


class RefreshSessionCreateSchema(BaseModel):
    refresh_token: uuid.UUID
    expires_in: int
    user_id: uuid.UUID


class RefreshSessionUpdateSchema(RefreshSessionCreateSchema):
    user_id: Optional[uuid.UUID] = Field(None)