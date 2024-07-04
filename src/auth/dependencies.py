import uuid

from fastapi import Depends
from jose import jwt

import config
from exceptions import InvalidTokenException
from auth.utils import OAuth2PasswordBearerWithCookie
from auth.schemas import UserSchema
from auth.service import UserService

oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl='/auth/login')


async def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> UserSchema:
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        user_id = payload.get('sub')
        if user_id is None:
            raise InvalidTokenException
    except Exception:
        raise InvalidTokenException
    current_user = await UserService.get_user(uuid.UUID(user_id))
    return current_user