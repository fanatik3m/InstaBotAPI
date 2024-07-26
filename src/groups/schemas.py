import datetime
import uuid
from typing import Optional, Dict, List, Union, Any

from pydantic import BaseModel, Field

from groups.utils import Status, ActionType


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


# class TaskCreateSchema(BaseModel):
#     group_name: str
#     function_names: List
#     args: List
#     execution_count: int
#     output: bool


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
    settings: Dict
    auto_reply_id: Optional[str]
    user_id: uuid.UUID
    group_id: uuid.UUID
    status: str

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


class TaskSchema(BaseModel):
    id: uuid.UUID
    pid: str
    status: Status
    action_type: ActionType
    time_start: datetime.datetime
    time_end: Optional[datetime.datetime]
    errors: Optional[Dict]
    output: Optional[Dict]
    client_id: uuid.UUID

    class Config:
        from_attributes = True


class TaskBaseSchema(BaseModel):
    status: Optional[Status] = Field(None)


class TaskCreateSchema(TaskBaseSchema):
    client_id: Optional[uuid.UUID] = Field(None)
    action_type: Optional[ActionType] = Field(None)
    pid: Optional[str] = Field(None)
    progress: Optional[str] = Field(None)


class TaskUpdateSchema(TaskBaseSchema):
    progress: Optional[str] = Field(None)
    errors: Optional[str] = Field(None)
    output: Optional[str] = Field(None)

    class Config:
        from_attributes = True


class TaskUpdateDBSchema(TaskUpdateSchema):
    time_end: Optional[datetime.datetime] = Field(None)


class TaskRequestBaseSchema(BaseModel):
    timeout_from: int
    timeout_to: int
    posts_timeout_from: int
    posts_timeout_to: int
    reels_timeout_from: int
    reels_timeout_to: int
    stories_timeout_from: int
    stories_timeout_to: int
    follow: bool
    stories_like: bool
    stories_amount: Optional[int] = Field(None)
    posts_like: bool
    posts_amount: Optional[int] = Field(None)
    reels_like: bool
    reels_amount: Optional[int] = Field(None)


class PeopleTaskRequestSchema(TaskRequestBaseSchema):
    users: List[str]


class HashtagsTaskRequestSchema(TaskRequestBaseSchema):
    hashtags: List[str]
    amount: int


class ParsingTaskRequestSchema(BaseModel):
    users: List[str]
    followers: bool
    followers_amount: Optional[int]
    followings: bool
    followings_amount: Optional[int]


class MixedTaskRequestSchema(BaseModel):
    people: bool
    people_config: PeopleTaskRequestSchema
    hashtags: bool
    hashtags_config: HashtagsTaskRequestSchema
    parsing: bool
    parsing_config: ParsingTaskRequestSchema
    timeout_from: int
    timeout_to: int
