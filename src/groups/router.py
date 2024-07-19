import uuid
from datetime import timedelta
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Body, Form, Request

from auth.dependencies import get_current_user
from auth.schemas import UserSchema
from groups.utils import add_text_randomize
from groups.service import GroupService, ClientService
from groups.schemas import TaskCreateSchema, SingleTaskCreateSchema, GroupSchema, GroupUpdateSchema, ClientSchema, \
    ClientUpdateSchema, CredentialsSchema, LoginClientSchema, UsersIdsTimeoutSchema, FollowingRequestSchema, \
    HashtagsTimeoutSchema, PeopleTaskRequestSchema, TaskUpdateSchema
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
    client_id = await ClientService.login_client(data.username, data.password, data.group, data.description, data.proxy,
                                                 user.id)
    return client_id


@client_router.post('/relogin')
async def relogin_client(credentials: CredentialsSchema, client_id: uuid.UUID = Body(...),
                         user: UserSchema = Depends(get_current_user)):
    client_id = await ClientService.relogin_client(client_id, credentials.username, credentials.password, user.id)
    return client_id


@client_router.post('/people/tasks/start/{client_id}')
async def create_people_task(client_id: uuid.UUID, request: Request, data: PeopleTaskRequestSchema,
                             redis=Depends(get_redis),
                             user: UserSchema = Depends(get_current_user)) -> uuid.UUID:
    task_id = await ClientService.create_people_task(client_id, data, request.base_url, redis, user.id)
    return task_id


@client_router.post('/people/tasks/pause/{task_id}')
async def pause_people_task(task_id: uuid.UUID, client_id: uuid.UUID = Body(...), redis=Depends(get_redis),
                            user: UserSchema = Depends(get_current_user)):
    await ClientService.pause_people_task(task_id, client_id, redis, user.id)


@client_router.post('/people/tasks/restart/{task_id}')
async def restart_people_task(task_id: uuid.UUID, client_id: uuid.UUID = Body(...), redis=Depends(get_redis),
                              user: UserSchema = Depends(get_current_user)):
    await ClientService.restart_people_task(task_id, client_id, redis, user.id)


@client_router.post('/people/tasks/stop/{task_id}')
async def stop_people_task(task_id: uuid.UUID, client_id: uuid.UUID = Body(...), redis=Depends(get_redis),
                           user: UserSchema = Depends(get_current_user)):
    await ClientService.stop_people_task(task_id, client_id, redis, user.id)


@client_router.put('/tasks/task/{task_id}')
async def edit_task(task_id: uuid.UUID, task: TaskUpdateSchema, redis=Depends(get_redis)):
    await ClientService.edit_task(task_id, task, redis)


@client_router.get('/tasks/client/{client_id}')
async def get_self_task(client_id: uuid.UUID, page: int = 1, user: UserSchema = Depends(get_current_user)):
    result = await ClientService.get_tasks(client_id, page, user.id)
    return result


@client_router.get('/tasks/task/{task_id}')
async def get_detail_task(task_id: uuid.UUID, user: UserSchema = Depends(get_current_user)):
    result = await ClientService.detail_task(task_id, user.id)
    return result


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


@client_router.delete('/auto-reply/{client_id}')
async def delete_auto_reply(client_id: uuid.UUID, user: UserSchema = Depends(get_current_user)):
    await ClientService.delete_auto_reply(client_id, user.id)


@client_router.get('/auto-reply/{client_id}')
async def get_has_client_auto_reply(client_id: uuid.UUID, user: UserSchema = Depends(get_current_user)) -> bool:
    result = await ClientService.get_auto_reply(client_id, user.id)
    return result


@client_router.post('/stories/like/{client_id}')
async def like_stories(client_id: uuid.UUID, data: UsersIdsTimeoutSchema, redis=Depends(get_redis),
                       user: UserSchema = Depends(get_current_user)):
    result = await ClientService.like_stories(client_id, data.users, data.timeout_from, data.timeout_to, redis,
                                              user.id)
    return result


@client_router.post('/posts/like/{client_id}')
async def first_post_like(client_id: uuid.UUID, data: UsersIdsTimeoutSchema, redis=Depends(get_redis),
                          user: UserSchema = Depends(get_current_user)):
    result = await ClientService.first_post_like(client_id, data.users, data.timeout_from, data.timeout_to, redis,
                                                 user.id)
    return result


@client_router.post('/reels/like/{client_id}')
async def reels_like(client_id: uuid.UUID, data: UsersIdsTimeoutSchema, amount: int = 20, redis=Depends(get_redis),
                     user: UserSchema = Depends(get_current_user)):
    result = await ClientService.reels_like(client_id, data.users, data.timeout_from, data.timeout_to, amount,
                                            redis, user.id)
    return result


@client_router.post('/hashtags/posts/like/{client_id}')
async def hashtags_like(client_id: uuid.UUID, data: HashtagsTimeoutSchema, amount: int = 20,
                        redis=Depends(get_redis), user: UserSchema = Depends(get_current_user)):
    result = await ClientService.hashtags_like(client_id, data.hashtags, data.timeout_from, data.timeout_to, amount,
                                               'groups/hashtags_posts_like_worker.py',
                                               redis, user.id)
    return result


@client_router.post('/hashtags/reels/like/{client_id}')
async def hashtags_reels_like(client_id: uuid.UUID, data: HashtagsTimeoutSchema, amount: int = 20,
                              redis=Depends(get_redis), user: UserSchema = Depends(get_current_user)):
    result = await ClientService.hashtags_like(client_id, data.hashtags, data.timeout_from, data.timeout_to, amount,
                                               'groups/hashtags_reels_like_worker.py',
                                               redis, user.id)
    return result


@client_router.post('/users/followings/{client_id}')
async def get_user_followings(client_id: uuid.UUID, users: List[str] = Body(...), amount: int = 20,
                              redis=Depends(get_redis), user: UserSchema = Depends(get_current_user)):
    result = await ClientService.user_followings(client_id, users, amount,
                                                 redis, user.id)
    return result


@client_router.post('/users/followers/{client_id}')
async def get_user_followers(client_id: uuid.UUID, users: List[str] = Body(...), amount: int = 20,
                             redis=Depends(get_redis), user: UserSchema = Depends(get_current_user)):
    result = await ClientService.user_followers(client_id, users, amount,
                                                redis, user.id)
    return result


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
