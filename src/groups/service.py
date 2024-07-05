import uuid
from typing import Optional, List

from fastapi import HTTPException, status
import docker
from instagrapi import Client

from groups.dao import GroupDAO, ClientDAO
from groups.schemas import GroupCreateDBSchema, TaskCreateSchema, ClientCreateDBSchema, SingleTaskCreateSchema
from database import async_session_maker


class GroupService:
    @classmethod
    async def create_group(cls, name: str, user_id: uuid.UUID) -> None:
        docker_client = docker.from_env()
        container = docker_client.containers.create('python:3.9')

        async with async_session_maker() as session:
            await GroupDAO.add(
                session,
                GroupCreateDBSchema(
                    name=name,
                    docker_name=container.name,
                    user_id=user_id
                )
            )
            await session.commit()

    @classmethod
    async def add_tasks(cls, group: str, tasks: List[SingleTaskCreateSchema], user_id: uuid.UUID,
                        output: bool = True) -> Optional[List]:
        docker_client = docker.from_env()
        output = output
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

            container = docker_client.containers.get(group.docker_name)

            for client in clients:
                for task in tasks:
                    for i in range(task.iteration_count):
                        exec_result = container.exec_run(
                            ['worker.py', task.function_name, client.settings, task.function_args[i]])
                        if output:
                            result.append(exec_result.output.decode('utf-8'))

            return result if output else None


class ClientService:
    @classmethod
    async def login_client(cls, username: str, password: str, user_id: uuid.UUID):
        client = Client()
        client.login(username, password)
        settings = client.get_settings()

        async with async_session_maker() as session:
            client_db = await ClientDAO.add(
                session,
                ClientCreateDBSchema(
                    settings=settings,
                    user_id=user_id
                )
            )
            result = client_db.id
            await session.commit()
            return result

    @classmethod
    async def add_tasks(cls, client_id: uuid.UUID, group: str, tasks: List[SingleTaskCreateSchema], user_id: uuid.UUID,
                        output: bool = True):
        docker_client = docker.from_env()
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

            container = docker_client.containers.get(group.docker_name)

            for task in tasks:
                for i in range(task.iteration_count):
                    exec_result = container.exec_run(
                        ['worker.py', task.function_name, client.settings, task.function_args[i]])
                    if output:
                        result.append(exec_result.output.decode('utf-8'))

            return result if output else None
