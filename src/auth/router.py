from fastapi import APIRouter, HTTPException, Depends

from auth.dependencies import get_current_user
from auth.schemas import UserCreateSchema, UserSchema
from auth.service import AuthService, UserService

router = APIRouter(
    prefix='/auth',
    tags=['Auth']
)


@router.post('/register')
async def register(user: UserCreateSchema):
    try:
        user = await UserService.register_user(user)
        return {
            'status': 'ok',
            'data': user
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': e
        }


@router.get('/me')
async def get_me(user: UserSchema = Depends(get_current_user)):
    try:
        return {
            'status': 'ok',
            'data': user
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': e
        }