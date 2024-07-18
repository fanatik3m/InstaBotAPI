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


def handle_stop(sign, frame):
    json_data = {
        'status': 'paused',
        'errors': json.dumps(errors),
        'logs': json.dumps(logs)
    }
    requests.put(url, json=json_data)


def handle_term(sign, frame):
    json_data = {
        'status': 'stopped',
        'time_end': datetime.utcnow(),
        'errors': json.dumps(errors),
        'logs': json.dumps(logs)
    }
    requests.put(url, json=json_data)
    exit()


signal.signal(signal.SIGSTOP, handle_stop)
signal.signal(signal.SIGTERM, handle_term)

for user in users:
    logs[user] = {}
    errors[user] = {}
    user_id = client.user_info_by_username_v1(user).pk
    if data.get('follow'):
        logs[user]['follow'] = False
        try:
            client.user_follow(user_id)
            logs[user]['follow'] = True
        except Exception as e:
            errors[user]['follow'] = str(e)[:50]
    if data.get('stories_like'):
        logs[user]['stories_like'] = 0
        errors[user]['stories_like'] = {}
        stories = client.user_stories(user_id, amount=data.get('stories_amount'))
        for story in stories:
            try:
                client.story_like(story.id)
                logs[user]['stories_like'] += 1
            except Exception as e:
                errors[user]['stories_like'][story.pk] = str(e)
    if data.get('posts_like'):
        logs[user]['posts_like'] = 0
        errors[user]['posts_like'] = {}
        try:
            posts = client.user_medias(user_id, amount=data.get('posts_amount'))
        except PrivateError:
            errors[user]['posts_like'] = 'Account is private'
        else:
            for post in posts:
                try:
                    client.media_like(post.id)
                    logs[user]['posts_like'] += 1
                except FeedbackRequired:
                    errors[user]['posts_like'][post.pk] = 'Too many requests, try later'
    if data.get('reels_like'):
        logs[user]['reels_like'] = 0
        errors[user]['reels_like'] = {}
        try:
            reels = client.user_clips(user_id, amount=data.get('reels_amount'))
        except PrivateError:
            errors[user]['reels_like'] = 'Account is private'
        else:
            for reel in reels:
                try:
                    client.media_like(reel.id)
                    logs[user]['reels_like'] += 1
                except FeedbackRequired:
                    errors[user]['reels_like'][reel.pk] = 'Too many requests, try later'

json_data = {
    'status': 'finished',
    'time_end': datetime.utcnow(),
    'errors': json.dumps(errors),
    'logs': json.dumps(logs)
}
requests.put(url, data=json_data)
