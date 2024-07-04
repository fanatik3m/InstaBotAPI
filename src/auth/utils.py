from typing import Optional, Dict

from passlib.context import CryptContext

from fastapi.security import OAuth2
from fastapi.openapi.models import OAuthFlows
from fastapi import Request, HTTPException, status
from fastapi.security.utils import get_authorization_scheme_param

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def is_valid_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


class OAuth2PasswordBearerWithCookie(OAuth2):
    def __init__(
        self,
        tokenUrl: str,
        scheme_name: Optional[str] = None,
        scopes: Optional[Dict[str, str]] = None,
        auto_error: bool = True
    ):
        if not scopes:
            scopes = {}
        flows = OAuthFlows(
            password={'tokenUrl': tokenUrl, 'scopes': scopes})
        super().__init__(flows=flows, scheme_name=scheme_name, auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[str]:
        authorization: str = request.cookies.get('access_token')

        scheme, param = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != 'bearer':
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail='Not authenticated',
                    headers={'WWW-Authenticate': 'Bearer'}
                )
            else:
                return None
        return param