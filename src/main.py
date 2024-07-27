import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.router import router as auth_router
from groups.router import group_router, client_router

sys.path.insert(1, os.path.join(sys.path[0], '..'))

app = FastAPI(
    title='InstaBot_API'
)

# add frontend when its location will be known
origins = ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth_router)
app.include_router(group_router)
app.include_router(client_router)
