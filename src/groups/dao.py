from dao.base import BaseDAO
from groups.models import GroupModel, ClientModel, TaskModel


class GroupDAO(BaseDAO):
    model = GroupModel


class ClientDAO(BaseDAO):
    model = ClientModel


class TaskDAO(BaseDAO):
    model = TaskModel