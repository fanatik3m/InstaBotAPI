import json
import signal
from datetime import datetime

from instagrapi import Client
from instagrapi.exceptions import PrivateError, FeedbackRequired

import requests

from ast import literal_eval

client = Client()
settings = literal_eval(str(settings))
client.set_settings(settings)
if proxy is not None:
    client.set_proxy(f'socks5://{proxy}')
client.delay_range = [timeout_from, timeout_to]
data = literal_eval(str(data))

errors = {}
logs = {}

paused = False


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

for user in users:
    logs[user] = {}
    errors[user] = {}
    user_id = client.user_info_by_username_v1(user).pk
    if data.get('followers'):
        try:
            followers = client.user_followers(user_id, amount=followers_amount)
            logs[user]['followers'] = [value.username for _, value in followers.items()]
        except Exception as e:
            errors[user]['followers'] = str(e)[:50]
    if data.get('followings'):
        try:
            followings = client.user_following(user_id, amount=following_amount)
            logs[user]['followings'] = [value.username for _, value in followings.items()]
        except Exception as e:
            errors[user]['followings'] = str(e)[:50]

json_data = {
    'status': 'finished',
    'errors': json.dumps(errors),
    'output': json.dumps(logs)
}
requests.put(url, json=json_data)
