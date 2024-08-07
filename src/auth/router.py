import uuid

from fastapi import APIRouter, HTTPException, Depends, Response, Request
from fastapi.security import OAuth2PasswordRequestForm

from auth.dependencies import get_current_user
from auth.schemas import UserCreateSchema, UserSchema, TokenSchema
from auth.service import AuthService, UserService
from auth.dao import UserDAO
from exceptions import InvalidCredentialsException
import config

router = APIRouter(
    prefix='/auth',
    tags=['Auth']
)


@router.post('/register')
async def register(user: UserCreateSchema) -> UserSchema:
    user = await UserService.register_user(user)
    return user


@router.get('/me')
async def get_me(user: UserSchema = Depends(get_current_user)) -> UserSchema:
    return user


@router.post('/login')
async def login(
        response: Response,
        credentials: OAuth2PasswordRequestForm = Depends()
) -> TokenSchema:
    user = await AuthService.authenticate_user(credentials.username, credentials.password)
    if not user:
        raise InvalidCredentialsException

    token = await AuthService.create_token(user.id)
    response.set_cookie(
        'access_token',
        token.access_token,
        max_age=int(config.ACCESS_TOKEN_EXPIRE_MINUTES) * 60,
        httponly=True
    )
    response.set_cookie(
        'refresh_token',
        str(token.refresh_token),
        max_age=int(config.REFRESH_TOKEN_EXPIRE_DAYS) * 24 * 60 * 60,
        httponly=True
    )
    return token


@router.post('/logout')
async def logout(
        request: Request,
        response: Response,
        user: UserSchema = Depends(get_current_user)
) -> str:
    response.delete_cookie('access_token')
    response.delete_cookie('refresh_token')

    await AuthService.logout(uuid.UUID(request.cookies.get('refresh_token')))
    return 'Logged out successfully'


@router.post('/abort')
async def abort_all_sessions(
        response: Response,
        user: UserSchema = Depends(get_current_user)
) -> str:
    response.delete_cookie('access_token')
    response.delete_cookie('refresh_token')

    await AuthService.abort_all_sessions(user.id)
    return 'All sessions were aborted'


@router.post('/refresh')
async def refresh_token(
    request: Request,
    response: Response
) -> TokenSchema:
    new_token = await AuthService.refresh_token(uuid.UUID(request.cookies.get('refresh_token')))

    response.set_cookie(
        'access_token',
        new_token.access_token,
        max_age=int(config.ACCESS_TOKEN_EXPIRE_MINUTES) * 60,
        httponly=True
    )
    response.set_cookie(
        'refresh_token',
        str(new_token.refresh_token),
        max_age=int(config.REFRESH_TOKEN_EXPIRE_DAYS) * 24 * 60 * 60,
        httponly=True
    )
    return new_token