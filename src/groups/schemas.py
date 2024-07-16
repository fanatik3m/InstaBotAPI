import uuid
from typing import Optional, Dict, List, Union, Any

from pydantic import BaseModel, Field


class GroupSchema(BaseModel):
    id: uuid.UUID
    name: str
    docker_id: str
    user_id: uuid.UUID

    class Config:
        from_attributes = True


class GroupBaseSchema(BaseModel):
    name: Optional[str] = Field(None)
    user_id: Optional[uuid.UUID] = Field(None)


class GroupCreateDBSchema(GroupBaseSchema):
    docker_id: str


class GroupUpdateSchema(BaseModel):
    name: str


class TaskCreateSchema(BaseModel):
    group_name: str
    function_names: List
    args: List
    execution_count: int
    output: bool


class SingleTaskCreateSchema(BaseModel):
    function_name: str
    function_args: List[List]
    iteration_count: int

    # function_args: [[arg1, arg2], [arg], [arg1, ..., arg n], ...]


class ClientSchema(BaseModel):
    id: uuid.UUID
    username: str
    photo: Optional[str]
    description: Optional[str]
    settings: str
    auto_reply_id: Optional[str]
    user_id: uuid.UUID
    group_id: uuid.UUID

    class Config:
        from_attributes = True


class ClientBaseSchema(BaseModel):
    settings: Optional[str] = Field(None)
    user_id: Optional[uuid.UUID] = Field(None)
    group_id: Optional[uuid.UUID] = Field(None)


class ClientCreateDBSchema(ClientBaseSchema):
    username: Optional[str] = Field(None)
    photo: Optional[str] = Field(None)
    proxy: Optional[str] = Field(None)
    description: Optional[str] = Field(None)


class ClientUpdateSchema(BaseModel):
    settings: Optional[str] = Field(None)
    description: Optional[str] = Field(None)


class CredentialsSchema(BaseModel):
    username: str
    password: str


class LoginClientSchema(CredentialsSchema):
    group: str
    proxy: Optional[str] = Field(None)
    description: Optional[str] = Field(None)


class FollowingResultSchema(BaseModel):
    followed: int
    total: int
    errors: Dict


class FollowingRequestSchema(BaseModel):
    users: List[str]
    timeout_from: int
    timeout_to: int


class TimeoutSchema(BaseModel):
    timeout_from: int
    timeout_to: int


class UsersIdsTimeoutSchema(TimeoutSchema):
    users: List[str]


class HashtagsTimeoutSchema(TimeoutSchema):
    hashtags: List[str]