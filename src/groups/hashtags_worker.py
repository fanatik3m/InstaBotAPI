import json
import signal
from datetime import datetime
import time
import random

from instagrapi import Client
from instagrapi.exceptions import PrivateError, FeedbackRequired

import requests

from ast import literal_eval

client = Client()
settings = literal_eval(str(settings))
client.set_settings(settings)
if proxy is not None:
    client.set_proxy(proxy)
data = literal_eval(str(data))

errors = {}
logs = {}
hashtags_processed = 0

paused = False

posts_timeout_from = data.get('posts_timeout_from')
posts_timeout_to = data.get('posts_timeout_to')
reels_timeout_from = data.get('reels_timeout_from')
reels_timeout_to = data.get('reels_timeout_to')
stories_timeout_from = data.get('stories_timeout_from')
stories_timeout_to = data.get('stories_timeout_to')


def handle_stop(sign, frame):
    global paused

    json_data = {
        'status': 'paused',
        'errors': json.dumps(errors),
        'output': json.dumps(logs),
        'progress': f'{hashtags_processed}/{hashtags_length}'
    }
    requests.put(url, json=json_data)
    paused = True
    while paused:
        signal.pause()


def handle_term(sign, frame):
    json_data = {
        'status': 'stopped',
        'errors': json.dumps(errors),
        'output': json.dumps(logs),
        'progress': f'{hashtags_processed}/{hashtags_length}'
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

hashtags_length = len(hashtags)


for hashtag in hashtags:
    posts = client.hashtag_medias_top(hashtag, amount=amount)
    users = [post.user.username for post in posts]

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
                time.sleep(random.randint(stories_timeout_from, stories_timeout_to))
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
                    time.sleep(random.randint(posts_timeout_from, posts_timeout_to))
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
                    time.sleep(random.randint(reels_timeout_from, reels_timeout_to))
                    try:
                        client.media_like(reel.id)
                        logs[user]['reels_like'] += 1
                    except FeedbackRequired:
                        errors[user]['reels_like'][reel.pk] = 'Too many requests, try later'
    hashtags_processed += 1
    time.sleep(random.randint(timeout_from, timeout_to))

json_data = {
    'status': 'finished',
    'errors': json.dumps(errors),
    'output': json.dumps(logs),
    'progress': f'{hashtags_processed}/{hashtags_length}'
}
requests.put(url, json=json_data)
