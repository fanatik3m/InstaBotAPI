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
    config: Mapped[str] = mapped_column(String, nullable=True)
    proxy: Mapped[str] = mapped_column(String, nullable=True)
    auto_reply_config: Mapped[str] = mapped_column(String, nullable=True)
    auto_reply_id: Mapped[str] = mapped_column(String, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('user.id', ondelete='CASCADE'))
    group_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('group.id', ondelete='CASCADE'))

    async def to_schema(self, redis):
        return ClientSchema(
            id=self.id,
            username=self.username,
            photo=self.photo,
            description=self.description,
            config=json.loads(self.config) if self.config else None,
            proxy=self.proxy,
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
    time_start: Mapped[time_start]
    time_end: Mapped[datetime.datetime] = mapped_column(nullable=True)
    errors: Mapped[str] = mapped_column(String, nullable=True)
    output: Mapped[str] = mapped_column(String, nullable=True)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('client.id', ondelete='CASCADE'))

    async def to_schema(self, redis):
        if self.action_type.value == 'parsing':
            progress_people = await redis.hget(str(self.id), 'progress')
            progress_people = progress_people.decode('utf-8') if progress_people else None
            status_people = await redis.hget(str(self.id), 'status')
            status_people = status_people.decode('utf-8') if status_people else None
            return TaskSchema(
                id=self.id,
                pid=self.pid,
                status=self.status,
                action_type=self.action_type,
                progress_people=progress_people,
                progress_hashtags=None,
                is_error_people=True if status_people == 'error' else False,
                is_error_hashtags=None,
                time_start=self.time_start,
                time_end=self.time_end,
                client_id=self.client_id
            )
        people = await redis.hget(str(self.id), 'status_people')
        hashtags = await redis.hget(str(self.id), 'status_hashtags')

        if people and hashtags:
            progress_people = await redis.hget(str(self.id), 'progress_people')
            progress_people = progress_people.decode('utf-8')
            progress_hashtags = await redis.hget(str(self.id), 'progress_hashtags')
            progress_hashtags = progress_hashtags.decode('utf-8')
            status_people = await redis.hget(str(self.id), 'status_people')
            status_people = status_people.decode('utf-8')
            status_hashtags = await redis.hget(str(self.id), 'status_hashtags')
            status_hashtags = status_hashtags.decode('utf-8')
        elif people and not hashtags:
            progress_people = await redis.hget(str(self.id), 'progress_people')
            progress_people = progress_people.decode('utf-8')
            progress_hashtags = None
            status_people = await redis.hget(str(self.id), 'status_people')
            status_people = status_people.decode('utf-8')
            status_hashtags = None
        elif hashtags:
            progress_people = None
            progress_hashtags = await redis.hget(str(self.id), 'progress_hashtags')
            progress_hashtags = progress_hashtags.decode('utf-8')
            status_people = None
            status_hashtags = await redis.hget(str(self.id), 'status_hashtags')
            status_hashtags = status_hashtags.decode('utf-8')

        return TaskSchema(
            id=self.id,
            pid=self.pid,
            status=self.status,
            action_type=self.action_type,
            progress_people=progress_people,
            progress_hashtags=progress_hashtags,
            is_error_people=True if status_people == 'error' else False,
            is_error_hashtags=True if status_hashtags == 'error' else False,
            time_start=self.time_start,
            time_end=self.time_end,
            client_id=self.client_id
        )