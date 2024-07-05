import uuid
from typing import List

from fastapi import APIRouter, Depends

from auth.dependencies import get_current_user
from auth.schemas import UserSchema
from groups.service import GroupService, ClientService
from groups.schemas import TaskCreateSchema, SingleTaskCreateSchema

group_router = APIRouter(
    prefix='/groups',
    tags=['Groups']
)
client_router = APIRouter(
    prefix='/clients',
    tags=['Clients']
)


@group_router.post('')
async def create_group(group: str, user: UserSchema = Depends(get_current_user)):
    try:
        await GroupService.create_group(group, user.id)
        return f'Created group {group}'
    except Exception as e:
        return e


# make single task schema and require list of these single-one schemas
@group_router.post('/tasks')
async def create_task_for_group(group: str, tasks: List[SingleTaskCreateSchema],
                                output: bool = True,
                                user: UserSchema = Depends(get_current_user)):
    try:
        result = await GroupService.add_tasks(group, tasks, user.id, output)
        return result
    except Exception as e:
        return e


@client_router.post('/login')
async def login_client(username: str, password: str, user: UserSchema = Depends(get_current_user)):
    try:
        client_id = await ClientService.login_client(username, password, user.id)
        return client_id
    except Exception as e:
        return e


@client_router.post('/tasks')
async def create_task_for_client(client_id: uuid.UUID, group: str, tasks: List[SingleTaskCreateSchema],
                                 output: bool = True,
                                 user: UserSchema = Depends(get_current_user)):
    try:
        result = await ClientService.add_tasks(client_id, group, tasks, user.id, output)
        return result
    except Exception as e:
        return e
