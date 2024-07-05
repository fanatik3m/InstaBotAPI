from dao.base import BaseDAO
from groups.models import GroupModel, ClientModel


class GroupDAO(BaseDAO):
    model = GroupModel


class ClientDAO(BaseDAO):
    model = ClientModel