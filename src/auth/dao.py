from auth.models import UserModel, RefreshSessionModel
from dao.base import BaseDAO


class UserDAO(BaseDAO):
    model = UserModel


class RefreshSessionDAO(BaseDAO):
    model = RefreshSessionModel