import uuid
from typing import Optional, List, Dict
import json
from datetime import timedelta, datetime

from fastapi import HTTPException, status
import docker
from instagrapi import Client
from instagrapi.types import HttpUrl
from sqlalchemy import select

from groups.dao import GroupDAO, ClientDAO, TaskDAO
from groups.schemas import GroupCreateDBSchema, TaskCreateSchema, ClientCreateDBSchema, SingleTaskCreateSchema, \
    GroupSchema, GroupUpdateSchema, ClientSchema, ClientUpdateSchema, PeopleTaskRequestSchema, TaskUpdateSchema, \
    TaskSchema, TaskUpdateDBSchema, HashtagsTaskRequestSchema, ParsingTaskRequestSchema, MixedTaskRequestSchema, \
    AutoReplyConfigSchema, ConfigSchema, TaskOutputSchema
from groups.models import GroupModel, ClientModel, TaskModel
from groups.utils import Pagination, is_valid_proxy, add_text_randomize
from database import async_session_maker


class GroupService:
    @classmethod
    async def create_group(cls, name: str, user_id: uuid.UUID) -> None:
        docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        container = docker_client.containers.run('python:3.10-alpine3.19', detach=True, tty=True, network_mode='host')
        container.exec_run('pip install instagrapi Pillow>=8.1 requests redis', detach=True)

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
                           proxy: Optional[str], redis, user_id: uuid.UUID):
        client = Client()
        if proxy is not None:
            client.set_proxy(proxy)

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
            await redis.set(str(result), 'active')
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
    async def get_config(cls, client_id: uuid.UUID, user_id: uuid.UUID) -> Optional[ConfigSchema]:
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

            if client.config:
                config = json.loads(client.config)
                return config
            return None

    @classmethod
    async def set_config(cls, client_id: uuid.UUID, config: ConfigSchema, user_id: uuid.UUID) -> None:
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

            config_data = config.model_dump()
            config_json = json.dumps(config_data)

            await ClientDAO.update(
                session,
                ClientModel.id == client_id,
                obj={
                    'config': config_json
                }
            )
            await session.commit()

    @classmethod
    async def get_auto_reply_config(cls, client_id: uuid.UUID, user_id: uuid.UUID) -> Optional[AutoReplyConfigSchema]:
        async with async_session_maker() as session:
            client = await ClientDAO.find_by_id(session, model_id=client_id)
            if client is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Config not found'
                )
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            if client.auto_reply_config:
                auto_reply_config = json.loads(client.auto_reply_config)
                return auto_reply_config
            return None

    @classmethod
    async def set_auto_reply_config(cls, client_id: uuid.UUID, auto_reply_config: AutoReplyConfigSchema,
                                    user_id: uuid.UUID) -> None:
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

            auto_reply_config_data = auto_reply_config.model_dump()
            auto_reply_config_json = json.dumps(auto_reply_config_data)

            await ClientDAO.update(
                session,
                ClientModel.id == client_id,
                obj={
                    'auto_reply_config': auto_reply_config_json
                }
            )

    @classmethod
    async def get_account_info(cls, client_id: uuid.UUID, user_id: uuid.UUID) -> Dict:
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

            settings = json.loads(client.settings)
            cl = Client()
            cl.set_settings(settings)
            if client.proxy is not None:
                client.set_proxy(client.proxy)

            info = cl.user_info_by_username_v1(client.username)
            return {
                'followers': info.follower_count,
                'followings': info.following_count
            }

    # @classmethod
    # async def create_people_task(cls, client_id: uuid.UUID, data: PeopleTaskRequestSchema, base_url: str, redis,
    #                              user_id: uuid.UUID) -> uuid.UUID:
    #     async with async_session_maker() as session:
    #         client = await ClientDAO.find_by_id(session, model_id=client_id)
    #         if client is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Client not found'
    #             )
    #         if client.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         group = await GroupDAO.find_by_id(session, model_id=client.group_id)
    #         if group.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    #         container = docker_client.containers.get(group.docker_id)
    #
    #         task = await TaskDAO.add(
    #             session,
    #             TaskCreateSchema(
    #                 status='working',
    #                 client_id=client_id,
    #                 action_type='people',
    #                 progress=f'0/{len(data.users)}'
    #             )
    #         )
    #         task_id = task.id
    #
    #         await redis.set(str(client.id), 'working')
    #
    #         with open('groups/people_worker.py', 'r') as file:
    #             command = file.read()
    #
    #         edit_url = str(base_url) + f'clients/tasks/task/{task_id}'
    #
    #         if client.proxy:
    #             command = f'settings = {json.loads(client.settings)}\nusers={data.users}\nurl="{edit_url}"\ntimeout_from={data.timeout_from}\ntimeout_to={data.timeout_to}\ndata={data.model_dump(exclude_unset=True)}\nproxy="{client.proxy}"\n{command}'.replace(
    #                 "\'", '"')
    #         else:
    #             command = f'settings = {json.loads(client.settings)}\nusers={data.users}\nurl="{edit_url}"\ntimeout_from={data.timeout_from}\ntimeout_to={data.timeout_to}\ndata={data.model_dump(exclude_unset=True)}\nproxy=None\n{command}'.replace(
    #                 "\'", '"')
    #
    #         exec_result = container.exec_run(['python', '-c', command], detach=True)
    #         ps = container.exec_run('ps aux').output.decode('utf-8')
    #         pid = ps.splitlines()[-2].strip()[:3].strip()
    #
    #         await TaskDAO.update(
    #             session,
    #             TaskModel.id == task_id,
    #             obj={'pid': pid}
    #         )
    #         await session.commit()
    #
    #         return task_id
    #
    # @classmethod
    # async def create_hashtags_task(cls, client_id: uuid.UUID, data: HashtagsTaskRequestSchema, base_url: str, redis,
    #                                user_id: uuid.UUID) -> uuid.UUID:
    #     async with async_session_maker() as session:
    #         client = await ClientDAO.find_by_id(session, model_id=client_id)
    #         if client is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Client not found'
    #             )
    #         if client.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         group = await GroupDAO.find_by_id(session, model_id=client.group_id)
    #         if group.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    #         container = docker_client.containers.get(group.docker_id)
    #
    #         task = await TaskDAO.add(
    #             session,
    #             TaskCreateSchema(
    #                 status='working',
    #                 client_id=client_id,
    #                 action_type='hashtag',
    #                 progress=f'0/{data.hashtags}'
    #             )
    #         )
    #         task_id = task.id
    #
    #         await redis.set(str(client.id), 'working')
    #
    #         with open('groups/hashtags_worker.py', 'r') as file:
    #             command = file.read()
    #
    #         edit_url = str(base_url) + f'clients/tasks/task/{task_id}'
    #
    #         if client.proxy:
    #             command = f'settings = {json.loads(client.settings)}\nhashtags={data.hashtags}\namount={data.amount}\nurl="{edit_url}"\ntimeout_from={data.timeout_from}\ntimeout_to={data.timeout_to}\ndata={data.model_dump(exclude_unset=True)}\nproxy="{client.proxy}"\n{command}'.replace(
    #                 "\'", '"')
    #         else:
    #             command = f'settings = {json.loads(client.settings)}\nhashtags={data.hashtags}\namount={data.amount}\nurl="{edit_url}"\ntimeout_from={data.timeout_from}\ntimeout_to={data.timeout_to}\ndata={data.model_dump(exclude_unset=True)}\nproxy=None\n{command}'.replace(
    #                 "\'", '"')
    #
    #         exec_result = container.exec_run(['python', '-c', command], detach=True)
    #         ps = container.exec_run('ps aux').output.decode('utf-8')
    #         pid = ps.splitlines()[-2].strip()[:3].strip()
    #
    #         await TaskDAO.update(
    #             session,
    #             TaskModel.id == task_id,
    #             obj={'pid': pid}
    #         )
    #         await session.commit()
    #
    #         return task_id
    #
    # @classmethod
    # async def create_parsing_task(cls, client_id: uuid.UUID, data: ParsingTaskRequestSchema, base_url: str, redis,
    #                               user_id: uuid.UUID) -> uuid.UUID:
    #     async with async_session_maker() as session:
    #         client = await ClientDAO.find_by_id(session, model_id=client_id)
    #         if client is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Client not found'
    #             )
    #         if client.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         group = await GroupDAO.find_by_id(session, model_id=client.group_id)
    #         if group.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    #         container = docker_client.containers.get(group.docker_id)
    #
    #         task = await TaskDAO.add(
    #             session,
    #             TaskCreateSchema(
    #                 status='working',
    #                 client_id=client_id,
    #                 action_type='parse',
    #                 progress=f'0/{len(data.users)}'
    #             )
    #         )
    #         task_id = task.id
    #
    #         await redis.set(str(client.id), 'working')
    #
    #         with open('groups/parse_worker.py', 'r') as file:
    #             command = file.read()
    #
    #         edit_url = str(base_url) + f'clients/tasks/task/{task_id}'
    #
    #         if client.proxy:
    #             command = f'settings = {json.loads(client.settings)}\nusers={data.users}\nurl="{edit_url}"\ndata={data.model_dump(exclude_unset=True)}\nproxy="{client.proxy}"\n{command}'.replace(
    #                 "\'", '"')
    #         else:
    #             command = f'settings = {json.loads(client.settings)}\nusers={data.users}\nurl="{edit_url}"\ndata={data.model_dump(exclude_unset=True)}\nproxy=None\n{command}'.replace(
    #                 "\'", '"')
    #
    #         exec_result = container.exec_run(['python', '-c', command], detach=True)
    #         ps = container.exec_run('ps aux').output.decode('utf-8')
    #         pid = ps.splitlines()[-2].strip()[:3].strip()
    #
    #         await TaskDAO.update(
    #             session,
    #             TaskModel.id == task_id,
    #             obj={'pid': pid}
    #         )
    #         await session.commit()
    #
    #         return task_id

    # @classmethod
    # async def create_mixed_task(cls, client_id: uuid.UUID, data: MixedTaskRequestSchema, base_url: str, redis,
    #                             user_id: uuid.UUID) -> uuid.UUID:
    #     async with async_session_maker() as session:
    #         client = await ClientDAO.find_by_id(session, model_id=client_id)
    #         if client is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Client not found'
    #             )
    #         if client.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         group = await GroupDAO.find_by_id(session, model_id=client.group_id)
    #         if group.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    #         container = docker_client.containers.get(group.docker_id)
    #
    #         progress_amount = 0
    #         if data.hashtags:
    #             progress_amount += len(data.hashtags_config.hashtags)
    #         if data.people:
    #             progress_amount += len(data.people_config.users)
    #         if data.parsing:
    #             progress_amount += len(data.parsing_config.users)
    #
    #         task = await TaskDAO.add(
    #             session,
    #             TaskCreateSchema(
    #                 status='working',
    #                 client_id=client_id,
    #                 action_type='mixed',
    #                 progress=f'0/{progress_amount}'
    #             )
    #         )
    #         task_id = task.id
    #
    #         await redis.set(str(client.id), 'working')
    #
    #         with open('groups/mixed_worker.py', 'r') as file:
    #             command = file.read()
    #
    #         edit_url = str(base_url) + f'clients/tasks/task/{task_id}'
    #
    #         if client.proxy:
    #             command = f'settings = {json.loads(client.settings)}\nurl="{edit_url}"\nprogress_amount={progress_amount}\ndata={data.model_dump(exclude_unset=True)}\nproxy="{client.proxy}"\n{command}'.replace(
    #                 "\'", '"')
    #         else:
    #             command = f'settings = {json.loads(client.settings)}\nurl="{edit_url}"\nprogress_amount={progress_amount}\ndata={data.model_dump(exclude_unset=True)}\nproxy=None\n{command}'.replace(
    #                 "\'", '"')
    #
    #         exec_result = container.exec_run(['python', '-c', command], detach=True)
    #         ps = container.exec_run('ps aux').output.decode('utf-8')
    #         pid = ps.splitlines()[-2].strip()[:3].strip()
    #
    #         await TaskDAO.update(
    #             session,
    #             TaskModel.id == task_id,
    #             obj={'pid': pid}
    #         )
    #         await session.commit()
    #
    #         return task_id

    @classmethod
    async def create_mixed_task(cls, clients_ids: List[uuid.UUID], base_url: str, redis,
                                user_id: uuid.UUID) -> List[uuid.UUID]:
        async with async_session_maker() as session:
            query = select(ClientModel).filter(ClientModel.id.in_(clients_ids), ClientModel.user_id == user_id)
            result = await session.execute(query)
            clients = result.scalars().all()

            if not clients:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Clients not found'
                )

            group = await GroupDAO.find_one(session, user_id=user_id)

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            tasks_ids = []
            for client in clients:
                config = json.loads(client.config)

                progress_amount = 0
                if config.get('hashtags'):
                    progress_amount += len(config.get('hashtags_config').get('hashtags'))
                if config.get('people'):
                    progress_amount += len(config.get('people_config').get('users'))
                if config.get('parsing'):
                    progress_amount += len(config.get('parsing_config').get('users'))

                task = await TaskDAO.add(
                    session,
                    TaskCreateSchema(
                        status='working',
                        client_id=client.id,
                        action_type='mixed'
                    )
                )
                task_id = task.id

                await redis.set(str(client.id), 'working')

                with open('groups/mixed_worker.py', 'r') as file:
                    command = file.read()

                edit_url = base_url + f'clients/tasks/task/{task_id}'

                if client.proxy:
                    command = f'settings = {json.loads(client.settings)}\nurl="{edit_url}"\ntask_id="{task_id}"\nprogress_amount={progress_amount}\ndata={config}\nproxy="{client.proxy}"\n{command}'.replace(
                        "\'", '"')
                else:
                    command = f'settings = {json.loads(client.settings)}\nurl="{edit_url}"\ntask_id="{task_id}"\nprogress_amount={progress_amount}\ndata={config}\nproxy=None\n{command}'.replace(
                        "\'", '"')

                exec_result = container.exec_run(['python', '-c', command], detach=True)
                ps = container.exec_run('ps aux').output.decode('utf-8')
                pid = ps.splitlines()[-2].strip()[:3].strip()

                await TaskDAO.update(
                    session,
                    TaskModel.id == task_id,
                    obj={'pid': pid}
                )

                tasks_ids.append(task_id)

            await session.commit()
            return tasks_ids

    # @classmethod
    # async def pause_task(cls, task_id: uuid.UUID, client_id: uuid.UUID, redis, user_id: uuid.UUID) -> None:
    #     async with async_session_maker() as session:
    #         task = await TaskDAO.find_by_id(session, model_id=task_id)
    #         if task is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Task not found'
    #             )
    #         if task.client_id != client_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         client = await ClientDAO.find_by_id(session, model_id=client_id)
    #         if client is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Client not found'
    #             )
    #         if client.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         group = await GroupDAO.find_by_id(session, model_id=client.group_id)
    #         if group is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Group not found'
    #             )
    #         if group.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    #         container = docker_client.containers.get(group.docker_id)
    #         if task.status.value == 'working':
    #             # container.exec_run(f'kill -STOP {task.pid}')
    #             container.exec_run(f'kill -SIGTSTP {task.pid}')

    @classmethod
    async def pause_task(cls, clients_ids: List[uuid.UUID], user_id: uuid.UUID) -> None:
        async with async_session_maker() as session:
            query = select(ClientModel.id).filter(ClientModel.id.in_(clients_ids), ClientModel.user_id == user_id)
            result = await session.execute(query)
            clients_ids = result.scalars().all()

            if not clients_ids:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Clients not found'
                )

            group = await GroupDAO.find_one(session, user_id=user_id)

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            for client_id in clients_ids:
                task = await TaskDAO.find_last(session, TaskModel.time_start, client_id=client_id)

                if task.status.value == 'working':
                    # container.exec_run(f'kill -STOP {task.pid}')
                    container.exec_run(f'kill -SIGTSTP {task.pid}')

    @classmethod
    async def restart_task(cls, clients_ids: List[uuid.UUID], user_id: uuid.UUID) -> None:
        async with async_session_maker() as session:
            query = select(ClientModel.id).filter(ClientModel.id.in_(clients_ids), ClientModel.user_id == user_id)
            result = await session.execute(query)
            clients_ids = result.scalars().all()

            if not clients_ids:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Clients not found'
                )

            group = await GroupDAO.find_one(session, user_id=user_id)

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            for client_id in clients_ids:
                task = await TaskDAO.find_last(session, TaskModel.time_start, client_id=client_id)

                if task.status.value == 'paused':
                    # container.exec_run(f'kill -CONT {task.pid}', detach=True)
                    container.exec_run(f'kill -SIGCONT {task.pid}')

                    await TaskDAO.update(
                        session,
                        TaskModel.id == task.id,
                        obj={'status': 'working'}
                    )
            await session.commit()

    @classmethod
    async def stop_task(cls, clients_ids: List[uuid.UUID], user_id: uuid.UUID) -> None:
        async with async_session_maker() as session:
            query = select(ClientModel.id).filter(ClientModel.id.in_(clients_ids), ClientModel.user_id == user_id)
            result = await session.execute(query)
            clients_ids = result.scalars().all()

            if not clients_ids:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Clients not found'
                )

            group = await GroupDAO.find_one(session, user_id=user_id)

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            for client_id in clients_ids:
                task = await TaskDAO.find_last(session, TaskModel.time_start, client_id=client_id)

                if task.status.value == 'working':
                    # container.exec_run(f'kill {task.pid}', detach=True)
                    container.exec_run(f'kill -SIGTERM {task.pid}')

    # @classmethod
    # async def restart_task(cls, task_id: uuid.UUID, client_id: uuid.UUID, redis, user_id: uuid.UUID) -> None:
    #     async with async_session_maker() as session:
    #         task = await TaskDAO.find_by_id(session, model_id=task_id)
    #         if task is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Task not found'
    #             )
    #         if task.client_id != client_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         client = await ClientDAO.find_by_id(session, model_id=client_id)
    #         if client is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Client not found'
    #             )
    #         if client.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         group = await GroupDAO.find_by_id(session, model_id=client.group_id)
    #         if group is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Group not found'
    #             )
    #         if group.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    #         container = docker_client.containers.get(group.docker_id)
    #
    #         if task.status.value == 'paused':
    #             # container.exec_run(f'kill -CONT {task.pid}', detach=True)
    #             container.exec_run(f'kill -SIGCONT {task.pid}')
    #
    #             await TaskDAO.update(
    #                 session,
    #                 TaskModel.id == task_id,
    #                 obj={'status': 'working'}
    #             )
    #             await session.commit()
    #
    # @classmethod
    # async def stop_task(cls, task_id: uuid.UUID, client_id: uuid.UUID, redis, user_id: uuid.UUID) -> None:
    #     async with async_session_maker() as session:
    #         task = await TaskDAO.find_by_id(session, model_id=task_id)
    #         if task is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Task not found'
    #             )
    #         if task.client_id != client_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         client = await ClientDAO.find_by_id(session, model_id=client_id)
    #         if client is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Client not found'
    #             )
    #         if client.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         group = await GroupDAO.find_by_id(session, model_id=client.group_id)
    #         if group is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Group not found'
    #             )
    #         if group.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    #         container = docker_client.containers.get(group.docker_id)
    #         if task.status.value == 'working':
    #             # container.exec_run(f'kill {task.pid}', detach=True)
    #             container.exec_run(f'kill -SIGTERM {task.pid}')

    @classmethod
    async def edit_task(cls, task_id: uuid.UUID, task: TaskUpdateSchema, redis):
        async with async_session_maker() as session:
            task_db = await TaskDAO.find_by_id(session, model_id=task_id)
            client = await ClientDAO.find_by_id(session, model_id=task_db.client_id)

            if task.status.value == 'finished' or task.status.value == 'stopped':
                await redis.set(str(client.id), 'active')

                await TaskDAO.update(
                    session,
                    TaskModel.id == task_id,
                    obj=TaskUpdateDBSchema(**task.model_dump(exclude_unset=True), time_end=datetime.utcnow())
                )
                await session.commit()
            elif task.status.value == 'paused':
                await redis.set(str(client.id), 'active')

                await TaskDAO.update(
                    session,
                    TaskModel.id == task_id,
                    obj=task
                )
                await session.commit()
            else:
                await redis.set(str(client.id), 'working')

    @classmethod
    async def get_tasks(cls, client_id: uuid.UUID, page: int, redis, user_id: uuid.UUID) -> Optional[List[TaskSchema]]:
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
                result = [await task.to_schema(redis) for task in tasks]
                return result
            return None

    @classmethod
    async def detail_task(cls, task_id: uuid.UUID, redis, user_id: uuid.UUID) -> TaskSchema:
        async with async_session_maker() as session:
            task = await TaskDAO.find_by_id(session, model_id=task_id)
            if task is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Task not found'
                )

            client = await ClientDAO.find_by_id(session, model_id=task.client_id)
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            result = await task.to_schema(redis)
            return result

    @classmethod
    async def get_logs(cls, task_id: uuid.UUID, user_id: uuid.UUID) -> Dict:
        async with async_session_maker() as session:
            task = await TaskDAO.find_by_id(session, model_id=task_id)
            if task is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Task not found'
                )

            client = await ClientDAO.find_by_id(session, model_id=task.client_id)
            if client.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN
                )

            result = {
                'logs': json.loads(task.output) if task.output else None,
                'errors': json.loads(task.errors) if task.errors else None
            }
            return result

    @classmethod
    async def get_status(cls, client_id: uuid.UUID, redis) -> str:
        client_status = await redis.get(str(client_id))
        return client_status

    # @classmethod
    # async def auto_reply(cls, client_id: uuid.UUID, text: str, no_dialogs_in: Dict, user_id: uuid.UUID) -> None:
    #     async with async_session_maker() as session:
    #         client = await ClientDAO.find_by_id(session, model_id=client_id)
    #         if client is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Client not found'
    #             )
    #         if client.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         group = await GroupDAO.find_by_id(session, model_id=client.group_id)
    #         if group.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         with open('groups/auto_reply_worker.py', 'r') as file:
    #             command = file.read()
    #
    #         if client.proxy:
    #             command = f'settings = {json.loads(client.settings)}\nno_dialogs_in={no_dialogs_in}\ntext="{text}"\nproxy="{client.proxy}"\n{command}'.replace(
    #                 "\'", '"')
    #         else:
    #             command = f'settings = {json.loads(client.settings)}\nno_dialogs_in={no_dialogs_in}\ntext="{text}"\nproxy=None\n{command}'.replace(
    #                 "\'", '"')
    #
    #         docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    #         container = docker_client.containers.get(group.docker_id)
    #
    #         # await redis.set(str(client.id), 'working')
    #
    #         container.exec_run(['python', '-c', command], detach=True)
    #         ps = container.exec_run('ps aux').output.decode('utf-8')
    #         pid = ps.splitlines()[-2].strip()[:3].strip()
    #
    #         await ClientDAO.update(
    #             session,
    #             ClientModel.id == client.id,
    #             obj={'auto_reply_id': pid}
    #         )
    #         await session.commit()

    @classmethod
    async def auto_reply(cls, clients_ids: List[uuid.UUID], user_id: uuid.UUID) -> None:
        async with async_session_maker() as session:
            query = select(ClientModel).filter(ClientModel.id.in_(clients_ids), ClientModel.user_id == user_id)
            result = await session.execute(query)
            clients = result.scalars().all()

            if not clients:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Clients not found'
                )

            group = await GroupDAO.find_one(session, user_id=user_id)

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            with open('groups/auto_reply_worker.py', 'r') as file:
                command = file.read()

            for client in clients:
                if client.auto_reply_id:
                    container.exec_run(f'kill {client.auto_reply_id}')
                else:
                    pass

                auto_reply_config = json.loads(client.auto_reply_config)
                text = auto_reply_config.get('text')
                timeout = auto_reply_config.get('timeout')

                if client.proxy:
                    worker_command = f'settings = {json.loads(client.settings)}\nno_dialogs_in={timeout}\ntext="{text}"\nproxy="{client.proxy}"\n{command}'.replace(
                        "\'", '"')
                else:
                    worker_command = f'settings = {json.loads(client.settings)}\nno_dialogs_in={timeout}\ntext="{text}"\nproxy=None\n{command}'.replace(
                        "\'", '"')

                docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
                container = docker_client.containers.get(group.docker_id)

                # await redis.set(str(client.id), 'working')

                container.exec_run(['python', '-c', worker_command], detach=True)
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
    async def delete_auto_reply(cls, clients_ids: List[uuid.UUID], user_id: uuid.UUID) -> None:
        async with async_session_maker() as session:
            query = select(ClientModel).filter(ClientModel.id.in_(clients_ids), ClientModel.user_id == user_id)
            result = await session.execute(query)
            clients = result.scalars().all()

            if not clients:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Clients not found'
                )

            group = await GroupDAO.find_one(session, user_id=user_id)

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(group.docker_id)

            for client in clients:
                container.exec_run(f'kill {client.auto_reply_id}')

                await ClientDAO.update(
                    session,
                    ClientModel.id == client.id,
                    obj={'auto_reply_id': None}
                )
            await session.commit()

    # @classmethod
    # async def delete_auto_reply(cls, client_id: uuid.UUID, user_id: uuid.UUID) -> None:
    #     async with async_session_maker() as session:
    #         client = await ClientDAO.find_by_id(session, model_id=client_id)
    #         if client is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Client not found'
    #             )
    #         if client.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         group = await GroupDAO.find_by_id(session, model_id=client.group_id)
    #         if group.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    #         container = docker_client.containers.get(group.docker_id)
    #         container.exec_run(f'kill {client.auto_reply_id}')
    #
    #         await ClientDAO.update(
    #             session,
    #             ClientModel.id == client.id,
    #             obj={'auto_reply_id': None}
    #         )
    #         await session.commit()

    # @classmethod
    # async def set_auto_reply(cls, clients_ids: List[uuid.UUID], user_id: uuid.UUID) -> None:
    #     async with async_session_maker() as session:
    #         query = select(ClientModel).filter(ClientModel.id.in_(clients_ids), ClientModel.user_id == user_id)
    #         result = await session.execute(query)
    #         clients = result.scalars().all()
    #
    #         if not clients:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Clients not found'
    #             )
    #
    #         group = await GroupDAO.find_one(session, user_id=user_id)
    #
    #         docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    #         container = docker_client.containers.get(group.docker_id)
    #
    #         with open('groups/auto_reply_worker.py', 'r') as file:
    #             command = file.read()
    #
    #         for client in clients:
    #             container.exec_run(f'kill {client.auto_reply_id}')
    #
    #             auto_reply_config = json.loads(client.auto_reply_config)
    #             text = auto_reply_config.get("text")
    #             timeout = auto_reply_config.get("timeout")
    #
    #             if client.proxy:
    #                 worker_command = f'settings = {json.loads(client.settings)}\nno_dialogs_in={timeout}\ntext="{text}"\nproxy="{client.proxy}"\n{command}'.replace(
    #                     "\'", '"')
    #             else:
    #                 worker_command = f'settings = {json.loads(client.settings)}\nno_dialogs_in={timeout}\ntext="{text}"\nproxy=None\n{command}'.replace(
    #                     "\'", '"')
    #
    #             # await redis.set(str(client.id), 'working')
    #
    #             exec_command = container.exec_run(['python', '-c', command], detach=True)
    #             ps = container.exec_run('ps aux').output.decode('utf-8')
    #             pid = ps.splitlines()[-2].strip()[:3].strip()
    #
    #             await ClientDAO.update(
    #                 session,
    #                 ClientModel.id == client.id,
    #                 obj={'auto_reply_id': pid}
    #             )
    #         await session.commit()

    # @classmethod
    # async def edit_auto_reply(cls, client_id: uuid.UUID, text: str, no_dialogs_in: Dict, user_id: uuid.UUID):
    #     async with async_session_maker() as session:
    #         client = await ClientDAO.find_by_id(session, model_id=client_id)
    #         if client is None:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail='Client not found'
    #             )
    #         if client.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         group = await GroupDAO.find_by_id(session, model_id=client.group_id)
    #         if group.user_id != user_id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_403_FORBIDDEN
    #             )
    #
    #         docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    #         container = docker_client.containers.get(group.docker_id)
    #         container.exec_run(f'kill {client.auto_reply_id}')
    #
    #         with open('groups/auto_reply_worker.py', 'r') as file:
    #             command = file.read()
    #
    #         if client.proxy:
    #             command = f'settings = {json.loads(client.settings)}\nno_dialogs_in={no_dialogs_in}\ntext="{text}"\nproxy="{client.proxy}"\n{command}'.replace(
    #                 "\'", '"')
    #         else:
    #             command = f'settings = {json.loads(client.settings)}\nno_dialogs_in={no_dialogs_in}\ntext="{text}"\nproxy=None\n{command}'.replace(
    #                 "\'", '"')
    #
    #         # await redis.set(str(client.id), 'working')
    #
    #         exec_command = container.exec_run(['python', '-c', command], detach=True)
    #         ps = container.exec_run('ps aux').output.decode('utf-8')
    #         pid = ps.splitlines()[-2].strip()[:3].strip()
    #
    #         await ClientDAO.update(
    #             session,
    #             ClientModel.id == client.id,
    #             obj={'auto_reply_id': pid}
    #         )
    #         await session.commit()

    @classmethod
    async def get_clients(cls, page: int, redis, user_id: uuid.UUID) -> Optional[List[ClientSchema]]:
        pagination = Pagination(page)

        async with async_session_maker() as session:
            clients = await ClientDAO.find_pagination(session, pagination.offset, pagination.limit, user_id=user_id)
            if not clients:
                return None

            result = [await client.to_schema(redis) for client in clients]
            return result

    @classmethod
    async def get_client_by_id(cls, client_id: uuid.UUID, redis, user_id: uuid.UUID) -> ClientSchema:
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

            result = await client.to_schema(redis)
            return result

    @classmethod
    async def edit_client_by_id(cls, client_id: uuid.UUID, client: ClientUpdateSchema, redis,
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
            result = await client_updated.to_schema(redis)
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
