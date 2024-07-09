import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends

from auth.dependencies import get_current_user
from auth.schemas import UserSchema
from groups.service import GroupService, ClientService
from groups.schemas import TaskCreateSchema, SingleTaskCreateSchema, GroupSchema, GroupUpdateSchema, ClientSchema, \
    ClientUpdateSchema

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


@group_router.get('')
async def get_self_groups(page: int = 1, user: UserSchema = Depends(get_current_user)) -> Optional[List[GroupSchema]]:
    groups = await GroupService.get_groups(page, user.id)
    return groups


@group_router.get('/{group_id}')
async def get_group_by_id(group_id: uuid.UUID, user: UserSchema = Depends(get_current_user)) -> GroupSchema:
    group = await GroupService.get_group_by_id(group_id, user.id)
    return group


@group_router.put('/{group_id}')
async def edit_group_name_by_id(group_id: uuid.UUID, group: GroupUpdateSchema,
                                user: UserSchema = Depends(get_current_user)) -> GroupSchema:
    group = await GroupService.edit_group_by_id(group_id, group, user.id)
    return group


@group_router.post('/tasks')
async def create_task_for_group(group: str, tasks: List[SingleTaskCreateSchema],
                                output: bool = True,
                                user: UserSchema = Depends(get_current_user)):
    try:
        result = await GroupService.add_tasks(group, tasks, user.id, output)
        return result
    except Exception as e:
        return e


@group_router.delete('/{group_id}')
async def delete_group_by_id(group_id: uuid.UUID, user: UserSchema = Depends(get_current_user)) -> None:
    await GroupService.delete_group_by_id(group_id, user.id)


@client_router.post('/login')
async def login_client(username: str, password: str, group: str, user: UserSchema = Depends(get_current_user)):
    try:
        client_id = await ClientService.login_client(username, password, group, user.id)
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


@client_router.get('')
async def get_self_clients(page: int = 1, user: UserSchema = Depends(get_current_user)) -> Optional[List[ClientSchema]]:
    clients = await ClientService.get_clients(page, user.id)
    return clients


@client_router.get('/{client_id}')
async def get_client_by_id(client_id: uuid.UUID, user: UserSchema = Depends(get_current_user)) -> ClientSchema:
    client = await ClientService.get_client_by_id(client_id, user.id)
    return client


@client_router.put('/{client_id}')
async def edit_client_settings_by_id(client_id: uuid.UUID, client: ClientUpdateSchema,
                                     user: UserSchema = Depends(get_current_user)) -> ClientSchema:
    client = await ClientService.edit_client_by_id(client_id, client, user.id)
    return client


@client_router.delete('/{client_id}')
async def delete_client_by_id(client_id: uuid.UUID, user: UserSchema = Depends(get_current_user)) -> None:
    await ClientService.delete_client_by_id(client_id, user.id)