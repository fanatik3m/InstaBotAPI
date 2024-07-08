import uuid
from typing import Optional, Dict, List, Union, Any

from pydantic import BaseModel, Field


class GroupSchema(BaseModel):
    id: uuid.UUID
    name: str
    docker_name: str
    user_id: uuid.UUID


class GroupBaseSchema(BaseModel):
    name: Optional[str] = Field(None)
    user_id: Optional[uuid.UUID] = Field(None)


class GroupCreateDBSchema(GroupBaseSchema):
    docker_id: str


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


class ClientBaseSchema(BaseModel):
    settings: Optional[str] = Field(None)
    user_id: Optional[uuid.UUID] = Field(None)
    group_id: Optional[uuid.UUID] = Field(None)


class ClientCreateDBSchema(ClientBaseSchema):
    pass