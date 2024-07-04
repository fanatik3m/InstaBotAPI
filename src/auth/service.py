import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from jose import jwt

import config
from exceptions import InvalidTokenException, TokenExpiredException
from auth.schemas import UserCreateSchema, UserCreateDBSchema, TokenSchema, RefreshSessionCreateSchema, \
    RefreshSessionUpdateSchema, UserSchema
from auth.models import UserModel, RefreshSessionModel
from database import async_session_maker
from auth.dao import UserDAO, RefreshSessionDAO
from auth.utils import get_password_hash, is_valid_password


class UserService:
    @classmethod
    async def register_user(cls, user: UserCreateSchema):
        async with async_session_maker() as session:
            user_exists = await UserDAO.find_one(session, username=user.username)
            if user_exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail='User already exists'
                )

            user_db = await UserDAO.add(
                session,
                UserCreateDBSchema(
                    **user.model_dump(),
                    hashed_password=get_password_hash(user.password)
                )
            )
            await session.commit()

            return user_db.to_schema()

    @classmethod
    async def get_user(cls, user_id: uuid.UUID) -> UserSchema:
        async with async_session_maker() as session:
            user = await UserDAO.find_one(session, id=user_id)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='User not found'
                )
            return user.to_schema()


class AuthService:
    @classmethod
    async def refresh_token(cls, refresh_token: uuid.UUID) -> TokenSchema:
        async with async_session_maker() as session:
            refresh_session = await RefreshSessionDAO.find_one(session, refresh_token=refresh_token)

            if refresh_session is None:
                raise InvalidTokenException
            if datetime.utcnow() > refresh_session.created_at + timedelta(days=refresh_session.expires_in):
                await RefreshSessionDAO.delete(session, id=refresh_session.id)
                raise TokenExpiredException

            user = await UserDAO.find_one(session, id=refresh_session.id)
            if user is None:
                raise InvalidTokenException

            access_token = cls._create_access_token(user_id=user.id)
            refresh_token = cls._create_refresh_token()
            refresh_token_expires = timedelta(
                days=config.REFRESH_TOKEN_EXPIRE_DAYS
            )

            await RefreshSessionDAO.update(
                session,
                RefreshSessionModel.id == refresh_session.id,
                obj=RefreshSessionUpdateSchema(
                    refresh_token=refresh_token,
                    expires_in=refresh_token_expires.total_seconds(),
                )
            )
            await session.commit()
        return TokenSchema(access_token=access_token, refresh_token=refresh_token, token_type='Bearer')

    @classmethod
    async def logout(cls, token: uuid.UUID):
        async with async_session_maker() as session:
            refresh_session = await RefreshSessionDAO.find_one(session, refresh_token=token)
            if refresh_session:
                await RefreshSessionDAO.delete(session, id=refresh_session.id)
                await session.commit()

    @classmethod
    async def abort_all_sessions(cls, user_id: uuid.UUID):
        async with async_session_maker() as session:
            await RefreshSessionDAO.delete(session, user_id=user_id)
            await session.commit()

    @classmethod
    async def create_token(cls, user_id: uuid.UUID) -> TokenSchema:
        access_token = cls._create_access_token(user_id)
        refresh_token = cls._create_refresh_token()
        refresh_token_expires = timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)

        async with async_session_maker() as session:
            await RefreshSessionDAO.add(
                session,
                RefreshSessionCreateSchema(
                    refresh_token=refresh_token,
                    expires_in=refresh_token_expires.total_seconds(),
                    user_id=user_id
                )
            )
            await session.commit()
        return TokenSchema(access_token=access_token, refresh_token=refresh_token, token_type='Bearer')

    @classmethod
    async def authenticate_user(cls, username: str, password: str) -> Optional[UserModel]:
        async with async_session_maker() as session:
            db_user = await UserDAO.find_one(session, username=username)
            if db_user and is_valid_password(password, db_user.hashed_password):
                return db_user
            return None

    @classmethod
    def _create_access_token(cls, user_id: uuid.UUID) -> str:
        to_encode = {
            'sub': str(user_id),
            'exp': datetime.utcnow() + timedelta(
                minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        }
        token = jwt.encode(
            to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM
        )
        return f'Bearer {token}'

    @classmethod
    def _create_refresh_token(cls) -> uuid.UUID:
        return uuid.uuid4()
