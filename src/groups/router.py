import uuid
from datetime import timedelta
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Body, Form, Request, HTTPException, status
from requests.exceptions import RetryError
from instagrapi.exceptions import LoginRequired

from auth.dependencies import get_current_user
from auth.schemas import UserSchema
from groups.utils import add_text_randomize, is_valid_proxy
from groups.service import GroupService, ClientService
from groups.schemas import TaskCreateSchema, SingleTaskCreateSchema, GroupSchema, GroupUpdateSchema, ClientSchema, \
    ClientUpdateSchema, CredentialsSchema, LoginClientSchema, UsersIdsTimeoutSchema, FollowingRequestSchema, \
    HashtagsTimeoutSchema, PeopleTaskRequestSchema, TaskUpdateSchema, HashtagsTaskRequestSchema, \
    ParsingTaskRequestSchema, MixedTaskRequestSchema, ConfigSchema, AutoReplyConfigSchema, AccountInfoSchema, \
    TaskSchema, TaskOutputSchema
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
    await GroupService.create_group(group, user.id)
    return f'Created group {group}'


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


@group_router.delete('/{group_id}')
async def delete_group_by_id(group_id: uuid.UUID, user: UserSchema = Depends(get_current_user)) -> None:
    await GroupService.delete_group_by_id(group_id, user.id)


@client_router.post('/login')
async def login_client(data: LoginClientSchema,
                       redis=Depends(get_redis),
                       user: UserSchema = Depends(get_current_user)) -> uuid.UUID:
    client_id = await ClientService.login_client(data.username, data.password, data.group, data.description, data.proxy,
                                                 redis, user.id)
    return client_id


@client_router.post('/relogin')
async def relogin_client(credentials: CredentialsSchema, client_id: uuid.UUID = Body(...),
                         user: UserSchema = Depends(get_current_user)) -> uuid.UUID:
    client_id = await ClientService.relogin_client(client_id, credentials.username, credentials.password, user.id)
    return client_id


@client_router.post('/proxy')
async def validate_proxy(proxy: str = Body(...)) -> bool:
    return is_valid_proxy(proxy)


@client_router.get('/account-info/{client_id}')
async def get_account_info(client_id: uuid.UUID, user: UserSchema = Depends(get_current_user)) -> AccountInfoSchema:
    try:
        account_info = await ClientService.get_account_info(client_id, user.id)
        return account_info
    except LoginRequired:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Instagram account requires login'
        )
    except RetryError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail='Too many requests, try later'
        )


@client_router.get('/config/client/{client_id}')
async def get_client_config(client_id: uuid.UUID,
                            user: UserSchema = Depends(get_current_user)) -> Optional[ConfigSchema]:
    config = await ClientService.get_config(client_id, user.id)
    return config


@client_router.post('/config/client/{client_id}')
async def set_client_config(client_id: uuid.UUID, config: ConfigSchema,
                            user: UserSchema = Depends(get_current_user)) -> None:
    await ClientService.set_config(client_id, config, user.id)


@client_router.get('/config/auto-reply/{client_id}')
async def get_auto_reply_config(client_id: uuid.UUID,
                                user: UserSchema = Depends(get_current_user)) -> Optional[AutoReplyConfigSchema]:
    auto_reply_config = await ClientService.get_auto_reply_config(client_id, user.id)
    return auto_reply_config


@client_router.post('/config/auto-reply/{client_id}')
async def set_auto_reply_config(client_id: uuid.UUID, config: AutoReplyConfigSchema,
                                user: UserSchema = Depends(get_current_user)) -> None:
    await ClientService.set_auto_reply_config(client_id, config, user.id)


# @client_router.post('/people/tasks/start/{client_id}')
# async def create_people_task(client_id: uuid.UUID, request: Request, data: PeopleTaskRequestSchema,
#                              redis=Depends(get_redis),
#                              user: UserSchema = Depends(get_current_user)) -> uuid.UUID:
#     task_id = await ClientService.create_people_task(client_id, data, request.base_url, redis, user.id)
#     return task_id
#
#
# @client_router.post('/hashtags/tasks/start/{client_id}')
# async def create_hashtags_task(client_id: uuid.UUID, request: Request, data: HashtagsTaskRequestSchema,
#                                redis=Depends(get_redis), user: UserSchema = Depends(get_current_user)):
#     task_id = await ClientService.create_hashtags_task(client_id, data, request.base_url, redis, user.id)
#     return task_id
#
#
# @client_router.post('/parsing/tasks/start/{client_id}')
# async def create_parsing_task(client_id: uuid.UUID, request: Request, data: ParsingTaskRequestSchema,
#                               redis=Depends(get_redis), user: UserSchema = Depends(get_current_user)):
#     task_id = await ClientService.create_parsing_task(client_id, data, request.base_url, redis, user.id)
#     return task_id
#
#
# @client_router.post('/mixed/tasks/start/{client_id}')
# async def create_mixed_task(client_id: uuid.UUID, request: Request, data: MixedTaskRequestSchema,
#                             redis=Depends(get_redis), user: UserSchema = Depends(get_current_user)):
#     task_id = await ClientService.create_mixed_task(client_id, data, request.base_url, redis, user.id)
#     return task_id

@client_router.post('/mixed/tasks/start/')
async def create_mixed_task(request: Request, clients_ids: List[uuid.UUID] = Body(...),
                            redis=Depends(get_redis), user: UserSchema = Depends(get_current_user)) -> List[uuid.UUID]:
    tasks_ids = await ClientService.create_mixed_task(clients_ids, str(request.base_url), redis, user.id)
    return tasks_ids


# @client_router.post('/tasks/pause/{task_id}')
# async def pause_task(task_id: uuid.UUID, client_id: uuid.UUID = Body(...), redis=Depends(get_redis),
#                      user: UserSchema = Depends(get_current_user)):
#     await ClientService.pause_task(task_id, client_id, redis, user.id)
#
#
# @client_router.post('/tasks/restart/{task_id}')
# async def restart_task(task_id: uuid.UUID, client_id: uuid.UUID = Body(...), redis=Depends(get_redis),
#                        user: UserSchema = Depends(get_current_user)):
#     await ClientService.restart_task(task_id, client_id, redis, user.id)
#
#
# @client_router.post('/tasks/stop/{task_id}')
# async def stop_task(task_id: uuid.UUID, client_id: uuid.UUID = Body(...), redis=Depends(get_redis),
#                     user: UserSchema = Depends(get_current_user)):
#     await ClientService.stop_task(task_id, client_id, redis, user.id)


@client_router.post('/tasks/pause')
async def pause_task(clients_ids: List[uuid.UUID] = Body(...), redis=Depends(get_redis),
                     user: UserSchema = Depends(get_current_user)) -> None:
    await ClientService.pause_task(clients_ids, redis, user.id)


@client_router.post('/tasks/restart')
async def restart_task(clients_ids: List[uuid.UUID] = Body(...), redis=Depends(get_redis),
                       user: UserSchema = Depends(get_current_user)) -> None:
    await ClientService.restart_task(clients_ids, redis, user.id)


@client_router.post('/tasks/stop')
async def stop_task(clients_ids: List[uuid.UUID] = Body(...), redis=Depends(get_redis),
                    user: UserSchema = Depends(get_current_user)) -> None:
    await ClientService.stop_task(clients_ids, redis, user.id)


@client_router.put('/tasks/task/{task_id}')
async def edit_task(task_id: uuid.UUID, task: TaskUpdateSchema, redis=Depends(get_redis)) -> None:
    await ClientService.edit_task(task_id, task, redis)


@client_router.get('/tasks/client/{client_id}')
async def get_self_task(client_id: uuid.UUID, page: int = 1,
                        redis=Depends(get_redis),
                        user: UserSchema = Depends(get_current_user)) -> Optional[List[TaskSchema]]:
    result = await ClientService.get_tasks(client_id, page, redis, user.id)
    return result


@client_router.get('/tasks/task/{task_id}')
async def get_detail_task(task_id: uuid.UUID, redis=Depends(get_redis),
                          user: UserSchema = Depends(get_current_user)) -> TaskSchema:
    result = await ClientService.detail_task(task_id, redis, user.id)
    return result


@client_router.get('/tasks/logs/{task_id}')
async def get_task_logs(task_id: uuid.UUID, user: UserSchema = Depends(get_current_user)) -> TaskOutputSchema:
    result = await ClientService.get_logs(task_id, user.id)
    return result


@client_router.get('/status/{client_id}', dependencies=[Depends(get_current_user)])
async def get_client_status(client_id: uuid.UUID, redis=Depends(get_redis)) -> str:
    status = await ClientService.get_status(client_id, redis)
    return status


# @client_router.post('/auto-reply/{client_id}')
# async def start_auto_reply(client_id: uuid.UUID, text: str = Body(...), followers_no_talk_time: Dict = Body(...),
#                            # redis=Depends(get_redis),
#                            user: UserSchema = Depends(get_current_user)):
#     await ClientService.auto_reply(client_id, text, followers_no_talk_time, user.id)

@client_router.post('/auto-reply')
async def set_auto_reply(clients_ids: List[uuid.UUID] = Body(...),
                         user: UserSchema = Depends(get_current_user)) -> None:
    await ClientService.auto_reply(clients_ids, user.id)


# @client_router.put('/auto-reply/{client_id}')
# async def edit_auto_reply(client_id: uuid.UUID, text: str = Body(...), followers_no_talk_time: Dict = Body(...),
#                           user: UserSchema = Depends(get_current_user)):
#     await ClientService.edit_auto_reply(client_id, text, followers_no_talk_time, user.id)

# @client_router.put('/auto-reply/{client_id}')
# async def edit_auto_reply(clients_ids: List[uuid.UUID] = Body(...),
#                           user: UserSchema = Depends(get_current_user)):
#     await ClientService.edit_auto_reply(clients_ids, user.id)


@client_router.delete('/auto-reply')
async def delete_auto_reply(clients_ids: List[uuid.UUID] = Body(...),
                            user: UserSchema = Depends(get_current_user)) -> None:
    await ClientService.delete_auto_reply(clients_ids, user.id)


@client_router.get('/auto-reply/{client_id}')
async def get_has_client_auto_reply(client_id: uuid.UUID, user: UserSchema = Depends(get_current_user)) -> bool:
    result = await ClientService.get_auto_reply(client_id, user.id)
    return result


@client_router.get('/operations/')
async def get_self_clients(page: int = 1, redis=Depends(get_redis), user: UserSchema = Depends(get_current_user)) -> \
        Optional[List[ClientSchema]]:
    clients = await ClientService.get_clients(page, redis, user.id)
    return clients


@client_router.get('/operations/{client_id}')
async def get_client_by_id(client_id: uuid.UUID, redis=Depends(get_redis),
                           user: UserSchema = Depends(get_current_user)) -> ClientSchema:
    client = await ClientService.get_client_by_id(client_id, redis, user.id)
    return client


@client_router.put('/operations/{client_id}')
async def edit_client_by_id(client_id: uuid.UUID, client: ClientUpdateSchema, redis=Depends(get_redis),
                            user: UserSchema = Depends(get_current_user)) -> ClientSchema:
    client = await ClientService.edit_client_by_id(client_id, client, redis, user.id)
    return client


# @client_router.delete('/operations/{client_id}')
# async def delete_client_by_id(client_id: uuid.UUID, user: UserSchema = Depends(get_current_user)) -> None:
#     await ClientService.delete_client_by_id(client_id, user.id)

@client_router.delete('/operations/')
async def delete_clients_by_id(clients_ids: List[uuid.UUID] = Body(...), redis=Depends(get_redis),
                               user: UserSchema = Depends(get_current_user)) -> None:
    await ClientService.delete_clients(clients_ids, redis, user.id)
