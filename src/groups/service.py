import uuid
from typing import Optional, List
import json

from fastapi import HTTPException, status
import docker
from instagrapi import Client

from groups.dao import GroupDAO, ClientDAO
from groups.schemas import GroupCreateDBSchema, TaskCreateSchema, ClientCreateDBSchema, SingleTaskCreateSchema, \
    GroupSchema, GroupUpdateSchema, ClientSchema, ClientUpdateSchema
from groups.models import GroupModel, ClientModel
from groups.utils import Pagination
from database import async_session_maker


class GroupService:
    @classmethod
    async def create_group(cls, name: str, user_id: uuid.UUID) -> None:
        docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        container = docker_client.containers.run('python:3.10', detach=True, tty=True)
        container.exec_run('pip install instagrapi Pillow>=8.1', detach=True)

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
                        command = f'settings = {json.loads(client.settings)}\nargs={task.function_args[i]}\nfunction_name="{task.function_name}"\n{command}'.replace(
                            "\'", '"')
                        exec_result = container.exec_run(['python', '-c', command])
                        # command = f'settings = {client.settings}\nargs={task.function_args[i]}\nfunction_name="{task.function_name}"\nclient = {Client()}\n{command}'
                        # exec_result = container.exec_run(['python', '-c', command])
                        if output:
                            result.append(exec_result.output.decode('utf-8')[:-1])

            return result if output else None

    @classmethod
    async def get_groups(cls, page: int, user_id: uuid.UUID) -> Optional[List[GroupSchema]]:
        limit: int = 10
        offset: int = limit * (page - 1)

        async with async_session_maker() as session:
            groups = await GroupDAO.find_pagination(session, offset, offset, user_id=user_id)
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

            docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            container = docker_client.containers.get(container_id)
            container.stop()
            container.remove()


class ClientService:
    @classmethod
    async def login_client(cls, username: str, password: str, group: str, user_id: uuid.UUID):
        client = Client()
        client.login(username, password)
        settings = client.get_settings()

        async with async_session_maker() as session:
            group_db = await GroupDAO.find_one(session, name=group)
            if group_db is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Group not found'
                )

            client_db = await ClientDAO.add(
                session,
                ClientCreateDBSchema(
                    settings=json.dumps(settings),
                    user_id=user_id,
                    group_id=group_db.id
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
                    command = f'settings = {json.loads(client.settings)}\nargs={task.function_args[i]}\nfunction_name="{task.function_name}"\n{command}'.replace(
                        "\'", '"')
                    exec_result = container.exec_run(['python', '-c', command])
                    # command = f'settings = {client.settings}\nargs={task.function_args[i]}\nfunction_name="{task.function_name}"\nclient = {Client()}\n{command}'
                    # exec_result = container.exec_run(['python', '-c', command])
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