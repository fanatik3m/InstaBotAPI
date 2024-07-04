from auth.models import UserModel
from dao.base import BaseDAO


class AuthDAO(BaseDAO):
    model = UserModel