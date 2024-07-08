import os
import sys

from fastapi import FastAPI

from auth.router import router as auth_router
from groups.router import group_router, client_router

sys.path.insert(1, os.path.join(sys.path[0], '..'))

app = FastAPI(
    title='InstaBot_API'
)

app.include_router(auth_router)
app.include_router(group_router)
app.include_router(client_router)
