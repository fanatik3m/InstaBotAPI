import uuid
from datetime import timedelta
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Body, Form

from auth.dependencies import get_current_user
from auth.schemas import UserSchema
from groups.utils import add_text_randomize
from groups.service import GroupService, ClientService
from groups.schemas import TaskCreateSchema, SingleTaskCreateSchema, GroupSchema, GroupUpdateSchema, ClientSchema, \
    ClientUpdateSchema, CredentialsSchema, LoginClientSchema, FollowingResultSchema, FollowingRequestSchema
from database import get_redis

group_router = APIRouter(
    prefix='/groups',
    tags=['Groups']
)
client_router = APIRouter(
    prefix='/clients',
    tags=['Clients']
)


@group_router.post('')
async def create_group(group: str = Body(...), user: UserSchema = Depends(get_current_user)):
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
async def create_task_for_group(tasks: List[SingleTaskCreateSchema], group: str = Body(...),
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
async def login_client(data: LoginClientSchema,
                       user: UserSchema = Depends(get_current_user)):
    client_id = await ClientService.login_client(data.username, data.password, data.group, data.description, data.proxy, user.id)
    return client_id


@client_router.post('/relogin')
async def relogin_client(credentials: CredentialsSchema, client_id: uuid.UUID = Body(...),
                         user: UserSchema = Depends(get_current_user)):
    client_id = await ClientService.relogin_client(client_id, credentials.username, credentials.password, user.id)
    return client_id


@client_router.post('/follow/{client_id}')
async def follow_users(client_id: uuid.UUID, data: FollowingRequestSchema, redis=Depends(get_redis),
                       user: UserSchema = Depends(get_current_user)):
    result = await ClientService.follow(client_id, data.users, data.timeout_from, data.timeout_to, user.id, redis)
    return result


@client_router.get('/status/{client_id}', dependencies=[Depends(get_current_user)])
async def get_client_status(client_id: uuid.UUID, redis=Depends(get_redis)) -> str:
    status = await ClientService.get_status(client_id, redis)
    return status


@client_router.post('/auto-reply/{client_id}')
async def start_auto_reply(client_id: uuid.UUID, text: str = Body(...), followers_no_talk_time: Dict = Body(...),
                           # redis=Depends(get_redis),
                           user: UserSchema = Depends(get_current_user)):
    await ClientService.auto_reply(client_id, text, followers_no_talk_time, user.id)


@client_router.put('/auto-reply/{client_id}')
async def edit_auto_reply(client_id: uuid.UUID, text: str = Body(...), followers_no_talk_time: Dict = Body(...),
                          user: UserSchema = Depends(get_current_user)):
    await ClientService.edit_auto_reply(client_id, text, followers_no_talk_time, user.id)


@client_router.post('/tasks')
async def create_task_for_client(tasks: List[SingleTaskCreateSchema], client_id: uuid.UUID = Body(...),
                                 group: str = Body(...),
                                 output: bool = True,
                                 user: UserSchema = Depends(get_current_user)):
    try:
        result = await ClientService.add_tasks(client_id, group, tasks, user.id, output)
        return result
    except Exception as e:
        return e


@client_router.get('/operations/')
async def get_self_clients(page: int = 1, user: UserSchema = Depends(get_current_user)) -> Optional[List[ClientSchema]]:
    clients = await ClientService.get_clients(page, user.id)
    return clients


@client_router.get('/operations/{client_id}')
async def get_client_by_id(client_id: uuid.UUID, user: UserSchema = Depends(get_current_user)) -> ClientSchema:
    client = await ClientService.get_client_by_id(client_id, user.id)
    return client


@client_router.put('/operations/{client_id}')
async def edit_client_by_id(client_id: uuid.UUID, client: ClientUpdateSchema,
                            user: UserSchema = Depends(get_current_user)) -> ClientSchema:
    client = await ClientService.edit_client_by_id(client_id, client, user.id)
    return client


@client_router.delete('/operations/{client_id}')
async def delete_client_by_id(client_id: uuid.UUID, user: UserSchema = Depends(get_current_user)) -> None:
    await ClientService.delete_client_by_id(client_id, user.id)
