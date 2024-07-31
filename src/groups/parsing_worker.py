import json
import signal
from datetime import datetime
import time
import random

import redis
from instagrapi import Client
from instagrapi.exceptions import PrivateError, FeedbackRequired, LoginRequired

import requests

from ast import literal_eval

client = Client()
settings = literal_eval(str(settings))
client.set_settings(settings)
if proxy is not None:
    client.set_proxy(proxy)
client.delay_range = [1, 3]
data = literal_eval(str(data))

redis = redis.Redis()

task_id = str(task_id)

progress_amount = len(data.get('users'))

errors = {}
logs = {}
progress_processed = 0

paused = False

is_error = False

parsing_followings = data.get('followings')
parsing_followings_amount = data.get('followings_amount')
parsing_followers = data.get('followers')
parsing_followers_amount = data.get('followers_amount')


def set_progress(error: bool, progress: int) -> None:
    if error:
        redis.hset(task_id, mapping={'status': 'error', 'progress': f'По людям: {progress}/{progress_amount}'})
    else:
        redis.hset(task_id, mapping={'status': 'ok', 'progress': f'По людям: {progress}/{progress_amount}'})


set_progress(error=False, progress=0)


def handle_stop(sign, frame):
    global paused

    json_data = {
        'status': 'paused',
        'errors': json.dumps(errors),
        'output': json.dumps(logs)
    }
    requests.put(url, json=json_data)
    paused = True
    while paused:
        signal.pause()


def handle_term(sign, frame):
    json_data = {
        'status': 'stopped',
        'errors': json.dumps(errors),
        'output': json.dumps(logs)
    }
    requests.put(url, json=json_data)
    exit()


def handle_resume(sign, frame):
    global paused

    json_data = {
        'status': 'working',
    }
    requests.put(url, json=json_data)
    paused = False


signal.signal(signal.SIGTSTP, handle_stop)
signal.signal(signal.SIGTERM, handle_term)
signal.signal(signal.SIGCONT, handle_resume)

logs['parsing'] = {}
errors['parsing'] = {}
for user in data.get('users'):
    logs['parsing'][user] = {}
    errors['parsing'][user] = {}
    try:
        user_id = client.user_info_by_username_v1(user).pk
    except LoginRequired:
        is_error = True
        errors['parsing'][user] = {'error': 'Login required'}
        set_progress(error=is_error, progress=progress_processed)
        break
    except Exception as e:
        is_error = True
        errors['parsing'][user] = {'error': str(e)[:50]}
        set_progress(error=is_error, progress=progress_processed)
        continue
    if parsing_followers:
        try:
            followers = client.user_followers(user_id, amount=parsing_followers_amount)
            logs['parsing'][user]['followers'] = [value.username for _, value in followers.items()]
        except Exception as e:
            is_error = True
            errors['parsing'][user]['followers'] = str(e)[:50]
    if parsing_followings:
        try:
            followings = client.user_following(user_id, amount=parsing_followings_amount)
            logs['parsing'][user]['followings'] = [value.username for _, value in followings.items()]
        except Exception as e:
            is_error = True
            errors['parsing'][user]['followings'] = str(e)[:50]
    progress_processed += 1
    set_progress(error=is_error, progress=progress_processed)

json_data = {
    'status': 'finished',
    'errors': json.dumps(errors),
    'output': json.dumps(logs)
}
requests.put(url, json=json_data)
