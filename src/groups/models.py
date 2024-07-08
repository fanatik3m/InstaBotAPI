import uuid

from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import String, ForeignKey, UniqueConstraint, JSON

from database import Base


class GroupModel(Base):
    __tablename__ = 'group'

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, index=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), index=True)
    docker_id: Mapped[str] = mapped_column(String, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('user.id', ondelete='CASCADE'))

    __table_args__ = (UniqueConstraint('name', 'user_id', name='unique_name_user_id'), )


class ClientModel(Base):
    __tablename__ = 'client'

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, index=True, default=uuid.uuid4)
    # settings: Mapped[dict] = mapped_column(JSON)
    settings: Mapped[str] = mapped_column(String)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('user.id', ondelete='CASCADE'))
    group_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('group.id', ondelete='CASCADE'))