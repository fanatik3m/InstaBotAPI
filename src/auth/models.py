import uuid

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from auth.orm_annotates import created_at, updated_at
from auth.schemas import UserSchema
from database import Base


class UserModel(Base):
    __tablename__ = 'user'

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, index=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    hashed_password: Mapped[str]
    created_at: Mapped[created_at]
    updated_at: Mapped[updated_at]

    def to_schema(self):
        return UserSchema(
            id=self.id,
            username=self.username,
            email=self.email,
            created_at=self.created_at,
            updated_at=self.updated_at
        )


class RefreshSessionModel(Base):
    __tablename__ = 'refresh_session'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    refresh_token: Mapped[uuid.UUID] = mapped_column(UUID, index=True)
    expires_in: Mapped[int]
    created_at: Mapped[created_at]
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('user.id', ondelete='CASCADE'))
