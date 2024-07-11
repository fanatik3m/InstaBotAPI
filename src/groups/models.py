import uuid

from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import String, ForeignKey, UniqueConstraint, JSON

from groups.schemas import GroupSchema, ClientSchema
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
    description: Mapped[str] = mapped_column(String)
    settings: Mapped[str] = mapped_column(String)
    proxy: Mapped[str] = mapped_column(String, nullable=True)
    auto_reply_id: Mapped[str] = mapped_column(String, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('user.id', ondelete='CASCADE'))
    group_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('group.id', ondelete='CASCADE'))

    def to_schema(self):
        return ClientSchema(
            id=self.id,
            settings=self.settings,
            user_id=self.user_id,
            group_id=self.group_id
        )