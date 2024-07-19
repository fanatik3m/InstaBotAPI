import uuid
from typing import Optional, List, Dict
import json
from datetime import timedelta

from fastapi import HTTPException, status
import docker
from instagrapi import Client
from instagrapi.types import HttpUrl

from groups.dao import GroupDAO, ClientDAO, TaskDAO
from groups.schemas import GroupCreateDBSchema, TaskCreateSchema, ClientCreateDBSchema, SingleTaskCreateSchema, \
    GroupSchema, GroupUpdateSchema, ClientSchema, ClientUpdateSchema, PeopleTaskRequestSchema, TaskUpdateSchema, \
    TaskSchema
from groups.models import GroupModel, ClientModel, TaskModel
from groups.utils import Pagination, is_valid_proxy, add_text_randomize
from database import async_session_maker


class GroupService:
    @classmethod
    async def create_group(cls, name: str, user_id: uuid.UUID) -> None:
        docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        container = docker_client.containers.run('python:3.10-alpine3.19', detach=True, tty=True, network_mode='host')
        container.exec_run('pip install instagrapi Pillow>=8.1 requests', detach=True)

        async with async_session_maker() as session:
            await GroupDAO.add(
                session,
                GroupCreateDBSchema(
                    name=name,
                    docker_id=container.id,
                    user_id=user_id
                )
            )
            await session.commit()

    @classmethod
    async def add_tasks(cls, group: str, tasks: List[SingleTaskCreateSchema], user_id: uuid.UUID,
                        output: bool = True) -> Optional[List]:
        docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        if output:
            result = []

        async with async_session_maker() as session:
            group = await GroupDAO.find_one(session, name=group)
            if group is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Group not found'
                )
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            clients = await ClientDAO.find_all(session, user_id=user_id, group_id=group.id)
            if not clients:
                return None

            container = docker_client.containers.get(group.docker_id)

            with open('groups/worker.py', 'r') as file:
                command = file.read()

            for client in clients:
                for task in tasks:
                    for i in range(task.iteration_count):
                        if client.proxy:
                            command = f'settings = {json.loads(client.settings)}\nargs={task.function_args[i]}\nfunction_name="{task.function_name}"\nproxy="{client.proxy}"\n{command}'.replace(
                                "\'", '"')
                        else:
                            command = f'settings = {json.loads(client.settings)}\nargs={task.function_args[i]}\nfunction_name="{task.function_name}"\nproxy=None\n{command}'.replace(
                                "\'", '"')
                        exec_result = container.exec_run(['python', '-c', command])
                        if output:
                            result.append(exec_result.output.decode('utf-8')[:-1])

            return result if output else None

    @classmethod
    async def get_groups(cls, page: int, user_id: uuid.UUID) -> Optional[List[GroupSchema]]:
        limit: int = 10
        offset: int = limit * (page - 1)

        async with async_session_maker() as session:
            groups = await GroupDAO.find_pagination(session, offset, limit, user_id=user_id)
            if not groups:
                return None

            result = [group.to_schema() for group in groups]
            return result

    @classmethod
    async def get_group_by_id(cls, group_id: uuid.UUID, user_id: uuid.UUID) -> GroupSchema:
        async with async_session_maker() as session:
            group = await GroupDAO.find_by_id(session, model_id=group_id)
            if group is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Group not found'
                )
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )
            result = group.to_schema()
            return result

    @classmethod
    async def edit_group_by_id(cls, group_id: uuid.UUID, group: GroupUpdateSchema, user_id: uuid.UUID) -> GroupSchema:
        async with async_session_maker() as session:
            group_db = await GroupDAO.find_by_id(session, model_id=group_id)
            if group_db is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Group not found'
                )
            if group_db.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group_updated = await GroupDAO.update(
                session,
                GroupModel.id == group_db.id,
                obj=group
            )
            result = group_updated.to_schema()
            await session.commit()

            return result

    @classmethod
    async def delete_group_by_id(cls, group_id: uuid.UUID, user_id: uuid.UUID) -> None:
        async with async_session_maker() as session:
            group = await GroupDAO.delete(session, id=group_id)
            if group is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Group not found'
                )
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            await ClientDAO.delete(session, group_id=group.id)
            container_id = group.docker_id
            await GroupDAO.delete(session, id=group.id)
            await session.commit()

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(container_id)
            container.stop()
            container.remove()


class ClientService:
    @classmethod
    async def login_client(cls, username: str, password: str, group: str, description: Optional[str],
                           proxy: Optional[str], user_id: uuid.UUID):
        client = Client()
        if proxy is not None:
            if is_valid_proxy(proxy):
                client.set_proxy(f'socks5://{proxy}')

        client.login(username, password)
        user_photo = client.user_info_by_username_v1(username).profile_pic_url
        photo_url = f'{user_photo.scheme}://{user_photo.host}:{user_photo.port}{user_photo.path}?{user_photo.query}'
        settings = client.get_settings()

        async with async_session_maker() as session:
            group_db = await GroupDAO.find_one(session, name=group, user_id=user_id)
            if group_db is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Group not found'
                )

            client_db = await ClientDAO.add(
                session,
                ClientCreateDBSchema(
                    username=username,
                    photo=photo_url,
                    description=description,
                    settings=json.dumps(settings),
                    user_id=user_id,
                    group_id=group_db.id,
                    proxy=proxy
                )
            )
            result = client_db.id
            await session.commit()
            return result

    @classmethod
    async def relogin_client(cls, client_id: uuid.UUID, username: str, password: str, user_id: uuid.UUID) -> uuid:
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            cl = Client()
            old_settings = json.loads(client.settings)
            cl.set_uuids(old_settings.get('uuids'))
            cl.login(username, password)

            new_settings = json.dumps(cl.get_settings())
            client_updated = await ClientDAO.update(
                session,
                ClientModel.id == client.id,
                obj={'settings': new_settings}
            )
            result = client_updated.id
            await session.commit()

            return result

    @classmethod
    async def create_people_task(cls, client_id: uuid.UUID, data: PeopleTaskRequestSchema, base_url: str, redis,
                                 user_id: uuid.UUID) -> uuid.UUID:
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_by_id(session, model_id=client.group_id)
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            task = await TaskDAO.add(
                session,
                TaskCreateSchema(
                    status='working',
                    client_id=client_id,
                    type='people'
                )
            )
            task_id = task.id
            await session.commit()

            await redis.set(str(client.id), 'working')

            with open('groups/people_worker.py', 'r') as file:
                command = file.read()

            edit_url = base_url + f'clients/tasks/{task_id}'

            if client.proxy:
                command = f'settings = {json.loads(client.settings)}\nusers={data.users}\nurl="{edit_url}"\ntimeout_from={data.timeout_from}\ntimeout_to={data.timeout_to}\ndata={data.model_dump(exclude_unset=True)}\nproxy="{client.proxy}"\n{command}'.replace(
                    "\'", '"')
            else:
                command = f'settings = {json.loads(client.settings)}\nusers={data.users}\nurl="{edit_url}"\ntimeout_from={data.timeout_from}\ntimeout_to={data.timeout_to}\ndata={data.model_dump(exclude_unset=True)}\nproxy=None\n{command}'.replace(
                    "\'", '"')

            exec_result = container.exec_run(['python', '-c', command], detach=True)
            return task_id

    @classmethod
    async def pause_people_task(cls, task_id: uuid.UUID, client_id: uuid.UUID, redis, user_id: uuid.UUID) -> None:
        async with async_session_maker() as session:
            task = await TaskDAO.find_by_id(session, model_id=task_id)
            if task is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if task.client_id != client_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_one(session, client_id=client_id)
            if group is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Group not found'
                )
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)
            container.exec_run(f'kill -STOP {task.pid}')

    @classmethod
    async def restart_people_task(cls, task_id: uuid.UUID, client_id: uuid.UUID, redis, user_id: uuid.UUID) -> None:
        async with async_session_maker() as session:
            task = await TaskDAO.find_by_id(session, model_id=task_id)
            if task is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if task.client_id != client_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_one(session, client_id=client_id)
            if group is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Group not found'
                )
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)
            container.exec_run(f'kill -CONT {task.pid}', detach=True)

            await TaskDAO.update(
                session,
                TaskModel.id == task_id,
                obj={'status': 'working'}
            )
            await session.commit()

    @classmethod
    async def stop_people_task(cls, task_id: uuid.UUID, client_id: uuid.UUID, redis, user_id: uuid.UUID) -> None:
        async with async_session_maker() as session:
            task = await TaskDAO.find_by_id(session, model_id=task_id)
            if task is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if task.client_id != client_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_one(session, client_id=client_id)
            if group is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Group not found'
                )
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)
            container.exec_run(f'kill {task.pid}', detach=True)

    @classmethod
    async def edit_task(cls, task_id: uuid.UUID, task: TaskUpdateSchema, redis):
        async with async_session_maker() as session:
            if task.status == 'finished':
                task = await TaskDAO.find_by_id(session, model_id=task_id)
                client = await ClientDAO.find_by_id(session, model_id=task.client_id)
                await redis.set(str(client.id), 'active')

            await TaskDAO.update(
                session,
                TaskModel.id == task_id,
                obj=task
            )
            await session.commit()

    @classmethod
    async def get_tasks(cls, client_id: uuid.UUID, page: int, user_id: uuid.UUID) -> Optional[List[TaskSchema]]:
        pagination = Pagination(page)

        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            tasks = await TaskDAO.find_pagination(session, offset=pagination.offset, limit=pagination.limit,
                                                  client_id=client_id)
            if tasks:
                result = [task.to_schema() for task in tasks]
                return result
            return None

    @classmethod
    async def detail_task(cls, task_id: uuid.UUID, user_id: uuid.UUID) -> TaskSchema:
        async with async_session_maker() as session:
            task = await TaskDAO.find_by_id(session, model_id=task_id)
            if task is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )

            client = await ClientDAO.find_by_id(session, model_id=task.client_id)
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            result = task.to_schema()
            return result

    @classmethod
    async def get_status(cls, client_id: uuid.UUID, redis) -> str:
        client_status = await redis.get(str(client_id))
        return client_status

    @classmethod
    async def follow(cls, client_id: uuid.UUID, users: List[str], timeout_from: int, timeout_to: int,
                     user_id: uuid.UUID, redis) -> Dict:
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_by_id(session, model_id=client.group_id)
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            await redis.set(str(client.id), 'working')

            with open('groups/follow_worker.py', 'r') as file:
                command = file.read()

            if client.proxy:
                command = f'settings = {json.loads(client.settings)}\nusers={users}\ntimeout_from={timeout_from}\ntimeout_to={timeout_to}\nproxy="{client.proxy}"\n{command}'.replace(
                    "\'", '"')
            else:
                command = f'settings = {json.loads(client.settings)}\nusers={users}\ntimeout_from={timeout_from}\ntimeout_to={timeout_to}\nproxy=None\n{command}'.replace(
                    "\'", '"')

            exec_result = container.exec_run(['python', '-c', command])
            errors = exec_result.output.decode('utf-8')
            errors = eval(errors[:-1])
            errors_count = len(errors.keys())
            users_count = len(users)

            result = {
                'followed': users_count - errors_count if (users_count - errors_count) > 0 else 0,
                'total': users_count,
                'errors': errors
            }

            await redis.set(str(client.id), 'active')

            return result

    @classmethod
    async def first_post_like(cls, client_id: uuid.UUID, users: List[str], timeout_from: int, timeout_to: int,
                              redis, user_id: uuid.UUID):
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_by_id(session, model_id=client.group_id)
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            await redis.set(str(client.id), 'working')

            with open('groups/first_post_like_worker.py', 'r') as file:
                command = file.read()

            if client.proxy:
                command = f'settings = {json.loads(client.settings)}\nusers={users}\ntimeout_from={timeout_from}\ntimeout_to={timeout_to}\nproxy="{client.proxy}"\n{command}'.replace(
                    "\'", '"')
            else:
                command = f'settings = {json.loads(client.settings)}\nusers={users}\ntimeout_from={timeout_from}\ntimeout_to={timeout_to}\nproxy=None\n{command}'.replace(
                    "\'", '"')

            exec_result = container.exec_run(['python', '-c', command])
            errors = exec_result.output.decode('utf-8')
            errors = eval(errors[:-1])
            errors_count = len(errors.keys())
            users_count = len(users)

            result = {
                'liked': users_count - errors_count if (users_count - errors_count) > 0 else 0,
                'total': users_count,
                'errors': errors
            }

            await redis.set(str(client.id), 'active')

            return result

    @classmethod
    async def reels_like(cls, client_id: uuid.UUID, users: List[str], timeout_from: int, timeout_to: int,
                         amount: int, redis, user_id: uuid.UUID):
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_by_id(session, model_id=client.group_id)
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            await redis.set(str(client.id), 'working')

            with open('groups/reels_like_worker.py', 'r') as file:
                command = file.read()

            if client.proxy:
                command = f'settings = {json.loads(client.settings)}\nusers={users}\ntimeout_from={timeout_from}\ntimeout_to={timeout_to}\namount={amount}\nproxy="{client.proxy}"\n{command}'.replace(
                    "\'", '"')
            else:
                command = f'settings = {json.loads(client.settings)}\nusers={users}\ntimeout_from={timeout_from}\ntimeout_to={timeout_to}\namount={amount}\nproxy=None\n{command}'.replace(
                    "\'", '"')

            exec_result = container.exec_run(['python', '-c', command])
            errors = exec_result.output.decode('utf-8')
            errors = eval(errors[:-1])
            errors_count = len(errors.keys())
            users_count = len(users)

            result = {
                'liked': users_count - errors_count if (users_count - errors_count) > 0 else 0,
                'total': users_count,
                'errors': errors
            }

            await redis.set(str(client.id), 'active')

            return result

    @classmethod
    async def hashtags_like(cls, client_id: uuid.UUID, hashtags: List[str], timeout_from: int, timeout_to: int,
                            amount: int, worker_path: str, redis,
                            user_id: uuid.UUID):
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_by_id(session, model_id=client.group_id)
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            await redis.set(str(client.id), 'working')

            with open(worker_path, 'r') as file:
                command = file.read()

            if client.proxy:
                command = f'settings = {json.loads(client.settings)}\nhashtags={hashtags}\ntimeout_from={timeout_from}\ntimeout_to={timeout_to}\namount={amount}\nproxy="{client.proxy}"\n{command}'.replace(
                    "\'", '"')
            else:
                command = f'settings = {json.loads(client.settings)}\nhashtags={hashtags}\ntimeout_from={timeout_from}\ntimeout_to={timeout_to}\namount={amount}\nproxy=None\n{command}'.replace(
                    "\'", '"')

            exec_result = container.exec_run(['python', '-c', command])
            errors = exec_result.output.decode('utf-8')
            errors = eval(errors[:-1])
            errors_count = len(errors.keys())
            hashtags_count = len(hashtags)

            result = {
                'liked': hashtags_count - errors_count if (hashtags_count - errors_count) > 0 else 0,
                'total': hashtags_count,
                'errors': errors
            }

            await redis.set(str(client.id), 'active')

            return result

    @classmethod
    async def user_followings(cls, client_id: uuid.UUID, users: List[str],
                              amount: int, redis, user_id: uuid.UUID):
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_by_id(session, model_id=client.group_id)
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            await redis.set(str(client.id), 'working')

            with open('groups/followings_parse_worker.py', 'r') as file:
                command = file.read()

            if client.proxy:
                command = f'settings = {json.loads(client.settings)}\nusers={users}\namount={amount}\nproxy="{client.proxy}"\n{command}'.replace(
                    "\'", '"')
            else:
                command = f'settings = {json.loads(client.settings)}\nusers={users}\namount={amount}\nproxy=None\n{command}'.replace(
                    "\'", '"')

            exec_result = container.exec_run(['python', '-c', command])
            callback = exec_result.output.decode('utf-8')
            callback = eval(callback[:-1])

            result = {
                'parsed': callback.get('parsed'),
                'errors': callback.get('error')
            }

            await redis.set(str(client.id), 'active')

            return result

    @classmethod
    async def user_followers(cls, client_id: uuid.UUID, users: List[str],
                             amount: int, redis, user_id: uuid.UUID):
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_by_id(session, model_id=client.group_id)
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            await redis.set(str(client.id), 'working')

            with open('groups/followers_parse_worker.py', 'r') as file:
                command = file.read()

            if client.proxy:
                command = f'settings = {json.loads(client.settings)}\nusers={users}\namount={amount}\nproxy="{client.proxy}"\n{command}'.replace(
                    "\'", '"')
            else:
                command = f'settings = {json.loads(client.settings)}\nusers={users}\namount={amount}\nproxy=None\n{command}'.replace(
                    "\'", '"')

            exec_result = container.exec_run(['python', '-c', command])
            callback = exec_result.output.decode('utf-8')
            callback = eval(callback[:-1])

            result = {
                'parsed': callback.get('parsed'),
                'errors': callback.get('error')
            }

            await redis.set(str(client.id), 'active')

            return result

    @classmethod
    async def auto_reply(cls, client_id: uuid.UUID, text: str, no_dialogs_in: Dict, user_id: uuid.UUID) -> None:
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_by_id(session, model_id=client.group_id)
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            with open('groups/auto_reply_worker.py', 'r') as file:
                command = file.read()

            if client.proxy:
                command = f'settings = {json.loads(client.settings)}\nno_dialogs_in={no_dialogs_in}\ntext="{text}"\nproxy="{client.proxy}"\n{command}'.replace(
                    "\'", '"')
            else:
                command = f'settings = {json.loads(client.settings)}\nno_dialogs_in={no_dialogs_in}\ntext="{text}"\nproxy=None\n{command}'.replace(
                    "\'", '"')

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            # await redis.set(str(client.id), 'working')

            container.exec_run(['python', '-c', command], detach=True)
            ps = container.exec_run('ps aux').output.decode('utf-8')
            pid = ps.splitlines()[-2].strip()[:3].strip()

            await ClientDAO.update(
                session,
                ClientModel.id == client.id,
                obj={'auto_reply_id': pid}
            )
            await session.commit()

    @classmethod
    async def get_auto_reply(cls, client_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            if client.auto_reply_id is not None:
                return True
            return False

    @classmethod
    async def delete_auto_reply(cls, client_id: uuid.UUID, user_id: uuid.UUID):
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_by_id(session, model_id=client.group_id)
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)
            container.exec_run(f'kill {client.auto_reply_id}')

            await ClientDAO.update(
                session,
                ClientModel.id == client.id,
                obj={'auto_reply_id': None}
            )
            await session.commit()

    @classmethod
    async def edit_auto_reply(cls, client_id: uuid.UUID, text: str, no_dialogs_in: Dict, user_id: uuid.UUID):
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_by_id(session, model_id=client.group_id)
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)
            container.exec_run(f'kill {client.auto_reply_id}')

            with open('groups/auto_reply_worker.py', 'r') as file:
                command = file.read()

            if client.proxy:
                command = f'settings = {json.loads(client.settings)}\nno_dialogs_in={no_dialogs_in}\ntext="{text}"\nproxy="{client.proxy}"\n{command}'.replace(
                    "\'", '"')
            else:
                command = f'settings = {json.loads(client.settings)}\nno_dialogs_in={no_dialogs_in}\ntext="{text}"\nproxy=None\n{command}'.replace(
                    "\'", '"')

            # await redis.set(str(client.id), 'working')

            exec_command = container.exec_run(['python', '-c', command], detach=True)
            ps = container.exec_run('ps aux').output.decode('utf-8')
            pid = ps.splitlines()[-2].strip()[:3].strip()

            await ClientDAO.update(
                session,
                ClientModel.id == client.id,
                obj={'auto_reply_id': pid}
            )
            await session.commit()

    @classmethod
    async def like_stories(cls, client_id: uuid.UUID, users: List[str], timeout_from: int, timeout_to: int, redis,
                           user_id: uuid.UUID):
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_by_id(session, model_id=client.group_id)
            if group.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            await redis.set(str(client.id), 'working')

            with open('groups/story_like_worker.py', 'r') as file:
                command = file.read()

            if client.proxy:
                command = f'settings = {json.loads(client.settings)}\nusers={users}\ntimeout_from={timeout_from}\ntimeout_to={timeout_to}\nproxy="{client.proxy}"\n{command}'.replace(
                    "\'", '"')
            else:
                command = f'settings = {json.loads(client.settings)}\nusers={users}\ntimeout_from={timeout_from}\ntimeout_to={timeout_to}\nproxy=None\n{command}'.replace(
                    "\'", '"')

            exec_result = container.exec_run(['python', '-c', command])
            callback = exec_result.output.decode('utf-8')
            callback = eval(callback[:-1])
            users_count = len(users)

            result = {
                'liked': callback.get('liked_count'),
                'users': users_count,
                'errors': callback.get('errors')
            }

            await redis.set(str(client.id), 'active')

            return result

    @classmethod
    async def add_tasks(cls, client_id: uuid.UUID, group: str, tasks: List[SingleTaskCreateSchema], user_id: uuid.UUID,
                        output: bool = True):
        docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        if output:
            result = []

        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            group = await GroupDAO.find_one(session, name=group)

            container = docker_client.containers.get(group.docker_id)
            with open('groups/worker.py', 'r') as file:
                command = file.read()

            for task in tasks:
                for i in range(task.iteration_count):
                    if client.proxy:
                        command = f'settings = {json.loads(client.settings)}\nargs={task.function_args[i]}\nfunction_name="{task.function_name}"\nproxy="{client.proxy}"\n{command}'.replace(
                            "\'", '"')
                    else:
                        command = f'settings = {json.loads(client.settings)}\nargs={task.function_args[i]}\nfunction_name="{task.function_name}"\nproxy=None\n{command}'.replace(
                            "\'", '"')
                        # command = f'settings = {json.loads(client.settings)}\nargs={task.function_args[i]}\nfunction_name="{task.function_name}"\n{command}'.replace(
                        #     "\'", '"')
                    exec_result = container.exec_run(['python', '-c', command])
                    if output:
                        result.append(exec_result.output.decode('utf-8')[:-1])

            return result if output else None

    @classmethod
    async def get_clients(cls, page: int, user_id: uuid.UUID) -> Optional[List[ClientSchema]]:
        pagination = Pagination(page)

        async with async_session_maker() as session:
            clients = await ClientDAO.find_pagination(session, pagination.offset, pagination.limit, user_id=user_id)
            if not clients:
                return None

            result = [client.to_schema() for client in clients]
            return result

    @classmethod
    async def get_client_by_id(cls, client_id: uuid.UUID, user_id: uuid.UUID) -> ClientSchema:
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            result = client.to_schema()
            return result

    @classmethod
    async def edit_client_by_id(cls, client_id: uuid.UUID, client: ClientUpdateSchema,
                                user_id: uuid.UUID) -> ClientSchema:
        async with async_session_maker() as session:
            client_db = await ClientDAO.find_by_id(session, model_id=client_id)
            if client_db is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client_db.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            client_updated = await ClientDAO.update(
                session,
                ClientModel.id == client_db.id,
                obj=client
            )
            result = client_updated.to_schema()
            await session.commit()

            return result

    @classmethod
    async def delete_client_by_id(cls, client_id: uuid.UUID, user_id: uuid.UUID) -> None:
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Client not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            await ClientDAO.delete(session, id=client.id)
            await session.commit()
