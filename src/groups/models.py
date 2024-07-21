import datetime
import uuid
import json

from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy import String, ForeignKey, UniqueConstraint, JSON

from groups.utils import Status, ActionType
from groups.orm_annotates import time_start
from groups.schemas import GroupSchema, ClientSchema, TaskSchema
from database import Base


class GroupModel(Base):
    __tablename__ = 'group'

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, index=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), index=True)
    docker_id: Mapped[str] = mapped_column(String, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('user.id', ondelete='CASCADE'))

    __table_args__ = (UniqueConstraint('name', 'user_id', name='unique_name_user_id'), )

    def to_schema(self):
        return GroupSchema(
            id=self.id,
            name=self.name,
            docker_id=self.docker_id,
            user_id=self.user_id
        )


class ClientModel(Base):
    __tablename__ = 'client'

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, index=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(128), unique=True)
    photo: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, nullable=True)
    settings: Mapped[str] = mapped_column(String)
    proxy: Mapped[str] = mapped_column(String, nullable=True)
    auto_reply_id: Mapped[str] = mapped_column(String, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('user.id', ondelete='CASCADE'))
    group_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('group.id', ondelete='CASCADE'))

    async def to_schema(self, redis):
        return ClientSchema(
            id=self.id,
            username=self.username,
            photo=self.photo,
            description=self.description,
            settings=json.loads(self.settings),
            auto_reply_id=self.auto_reply_id,
            user_id=self.user_id,
            group_id=self.group_id,
            status=await redis.get(str(self.id))
        )


class TaskModel(Base):
    __tablename__ = 'task'

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, index=True, default=uuid.uuid4)
    pid: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[Status]
    action_type: Mapped[ActionType]
    progress: Mapped[str] = mapped_column(String(32))
    time_start: Mapped[time_start]
    time_end: Mapped[datetime.datetime] = mapped_column(nullable=True)
    errors: Mapped[str] = mapped_column(String, nullable=True)
    output: Mapped[str] = mapped_column(String, nullable=True)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('client.id', ondelete='CASCADE'))

    def to_schema(self):
        return TaskSchema(
            id=self.id,
            pid=self.pid,
            status=self.status,
            action_type=self.action_type,
            time_start=self.time_start,
            time_end=self.time_end,
            errors=json.loads(self.errors) if self.errors else None,
            output=json.loads(self.output) if self.output else None,
            client_id=self.client_id
        )