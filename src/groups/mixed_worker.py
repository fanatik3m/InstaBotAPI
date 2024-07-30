import json
import signal
from datetime import datetime
import time
import random
from typing import Optional

import redis
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

redis = redis.Redis()

task_id = str(task_id)

errors = {}
logs = {}

paused = False

is_error_people = False
is_error_hashtags = False

people = data.get('people')
hashtags = data.get('hashtags')

if people and hashtags:
    action = 0
    progress_people = 0
    progress_hashtags = 0
elif people and not hashtags:
    action = 1
    progress_people = 0
    progress_hashtags = None
elif hashtags:
    action = 2
    progress_people = None
    progress_hashtags = 0

if people:
    users = data.get('people_config').get('users')
    users_length = len(users)
    people_timeout_from = data.get('people_config').get('timeout_from')
    people_timeout_to = data.get('people_config').get('timeout_to')
    people_posts_timeout_from = data.get('people_config').get('posts_timeout_from')
    people_posts_timeout_to = data.get('people_config').get('posts_timeout_to')
    people_reels_timeout_from = data.get('people_config').get('reels_timeout_from')
    people_reels_timeout_to = data.get('people_config').get('reels_timeout_to')
    people_stories_timeout_from = data.get('people_config').get('stories_timeout_from')
    people_stories_timeout_to = data.get('people_config').get('stories_timeout_to')
    people_follow = data.get('people_config').get('follow')
    people_stories_like = data.get('people_config').get('stories_like')
    people_reels_like = data.get('people_config').get('reels_like')
    people_posts_like = data.get('people_config').get('posts_like')
    people_stories_amount = data.get('people_config').get('stories_amount')
    people_reels_amount = data.get('people_config').get('reels_amount')
    people_posts_amount = data.get('people_config').get('posts_amount')
if hashtags:
    hashtags = data.get('hashtags_config').get('hashtags')
    hashtags_length = len(hashtags)
    hashtags_timeout_from = data.get('hashtags_config').get('timeout_from')
    hashtags_timeout_to = data.get('hashtags_config').get('timeout_to')
    hashtags_posts_timeout_from = data.get('hashtags_config').get('posts_timeout_from')
    hashtags_posts_timeout_to = data.get('hashtags_config').get('posts_timeout_to')
    hashtags_reels_timeout_from = data.get('hashtags_config').get('reels_timeout_from')
    hashtags_reels_timeout_to = data.get('hashtags_config').get('reels_timeout_to')
    hashtags_stories_timeout_from = data.get('hashtags_config').get('stories_timeout_from')
    hashtags_stories_timeout_to = data.get('hashtags_config').get('stories_timeout_to')
    hashtags_follow = data.get('hashtags_config').get('follow')
    hashtags_stories_like = data.get('hashtags_config').get('stories_like')
    hashtags_reels_like = data.get('hashtags_config').get('reels_like')
    hashtags_posts_like = data.get('hashtags_config').get('posts_like')
    hashtags_stories_amount = data.get('hashtags_config').get('stories_amount')
    hashtags_reels_amount = data.get('hashtags_config').get('reels_amount')
    hashtags_posts_amount = data.get('hashtags_config').get('posts_amount')


def set_progress(error_people: bool, error_hashtags, action_type: int, people_processed: Optional[int] = None,
                 hashtags_processed: Optional[int] = None) -> None:
    status_people = 'error' if error_people else 'ok'
    status_hashtags = 'error' if error_hashtags else 'ok'
    if action_type == 0:
        redis.hset(task_id, mapping={'status_people': status_people,
                                     'status_hashtags': status_hashtags,
                                     'progress_people': f'По людям: {people_processed}/{users_length}',
                                     'progress_hashtags': f'По хештегам: {hashtags_processed}/{hashtags_length}'
                                     })
    elif action_type == 1:
        redis.hset(task_id, mapping={'status_people': status_people,
                                     'progress_people': f'По людям: {people_processed}/{users_length}'
                                     })
    else:
        redis.hset(task_id, mapping={
            'status_hashtags': status_hashtags,
            'progress_people': f'По хештегам: {hashtags_processed}/{hashtags_length}'
        })


set_progress(error_people=False, error_hashtags=False, action_type=action, people_processed=progress_people,
             hashtags_processed=progress_hashtags)


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

if people:
    logs['people'] = {}
    errors['people'] = {}
    for user in users:
        logs['people'][user] = {}
        errors['people'][user] = {}
        user_id = client.user_info_by_username_v1(user).pk
        if people_follow:
            logs['people'][user]['follow'] = False
            try:
                client.user_follow(user_id)
                logs['people'][user]['follow'] = True
            except Exception as e:
                is_error_people = True
                errors['people'][user]['follow'] = str(e)[:50]
        if people_stories_like:
            logs['people'][user]['stories_like'] = 0
            errors['people'][user]['stories_like'] = {}
            stories = client.user_stories(user_id, amount=people_stories_amount)
            for story in stories:
                time.sleep(random.randint(people_stories_timeout_from, people_stories_timeout_to))
                try:
                    client.story_like(story.id)
                    logs['people'][user]['stories_like'] += 1
                except Exception as e:
                    is_error_people = True
                    errors['people'][user]['stories_like'][story.pk] = str(e)
        if people_posts_like:
            logs['people'][user]['posts_like'] = 0
            errors['people'][user]['posts_like'] = {}
            try:
                posts = client.user_medias(user_id, amount=people_posts_amount)
            except PrivateError:
                is_error_people = True
                errors['people'][user]['posts_like'] = 'Account is private'
            else:
                for post in posts:
                    time.sleep(random.randint(people_posts_timeout_from, people_posts_timeout_to))
                    try:
                        client.media_like(post.id)
                        logs['people'][user]['posts_like'] += 1
                    except FeedbackRequired:
                        is_error_people = True
                        errors['people'][user]['posts_like'][post.pk] = 'Too many requests, try later'
        if people_reels_like:
            logs['people'][user]['reels_like'] = 0
            errors['people'][user]['reels_like'] = {}
            try:
                reels = client.user_clips(user_id, amount=people_reels_amount)
            except PrivateError:
                is_error_people = True
                errors['people'][user]['reels_like'] = 'Account is private'
            else:
                for reel in reels:
                    time.sleep(random.randint(people_reels_timeout_from, people_reels_timeout_to))
                    try:
                        client.media_like(reel.id)
                        logs['people'][user]['reels_like'] += 1
                    except FeedbackRequired:
                        is_error_people = True
                        errors[user]['reels_like'][reel.pk] = 'Too many requests, try later'
        progress_people += 1
        set_progress(error_people=is_error_people, error_hashtags=is_error_hashtags, action_type=action,
                     people_processed=progress_people,
                     hashtags_processed=progress_hashtags)
        time.sleep(random.randint(people_timeout_from, people_timeout_to))

time.sleep(random.randint(5, 10))

if hashtags:
    logs['hashtags'] = {}
    errors['hashtags'] = {}
    hashtags_amount = data.get('hashtags_config').get('amount')
    for hashtag in hashtags:
        try:
            posts = client.hashtag_medias_top(hashtag, amount=hashtags_amount)
            users = [post.user.username for post in posts]
        except Exception as e:
            is_error_hashtags = True
            errors['hashtags'] = str(e)[:50]
            set_progress(error_people=is_error_people, error_hashtags=is_error_hashtags, action_type=action,
                         people_processed=progress_people,
                         hashtags_processed=progress_hashtags)
            break

        for user in users:
            logs['hashtags'][user] = {}
            errors['hashtags'][user] = {}
            user_id = client.user_info_by_username_v1(user).pk
            if hashtags_follow:
                logs['hashtags'][user]['follow'] = False
                try:
                    client.user_follow(user_id)
                    logs['hashtags'][user]['follow'] = True
                except Exception as e:
                    is_error_hashtags = True
                    errors['hashtags'][user]['follow'] = str(e)[:50]
            if hashtags_stories_like:
                logs['hashtags'][user]['stories_like'] = 0
                errors['hashtags'][user]['stories_like'] = {}
                stories = client.user_stories(user_id, amount=hashtags_stories_amount)
                for story in stories:
                    time.sleep(random.randint(hashtags_stories_timeout_from, hashtags_stories_timeout_to))
                    try:
                        client.story_like(story.id)
                        logs['hashtags'][user]['stories_like'] += 1
                    except Exception as e:
                        is_error_hashtags = True
                        errors['hashtags'][user]['stories_like'][story.pk] = str(e)
            if hashtags_posts_like:
                logs['hashtags'][user]['posts_like'] = 0
                errors['hashtags'][user]['posts_like'] = {}
                try:
                    posts = client.user_medias(user_id, amount=hashtags_posts_amount)
                except PrivateError:
                    is_error_hashtags = True
                    errors['hashtags'][user]['posts_like'] = 'Account is private'
                else:
                    for post in posts:
                        time.sleep(random.randint(hashtags_posts_timeout_from, hashtags_posts_timeout_to))
                        try:
                            client.media_like(post.id)
                            logs['hashtags'][user]['posts_like'] += 1
                        except FeedbackRequired:
                            is_error_hashtags = True
                            errors['hashtags'][user]['posts_like'][post.pk] = 'Too many requests, try later'
            if hashtags_reels_like:
                logs['hashtags'][user]['reels_like'] = 0
                errors['hashtags'][user]['reels_like'] = {}
                try:
                    reels = client.user_clips(user_id, hashtags_reels_amount)
                except PrivateError:
                    is_error_hashtags = True
                    errors['hashtags'][user]['reels_like'] = 'Account is private'
                else:
                    for reel in reels:
                        time.sleep(random.randint(hashtags_reels_timeout_from, hashtags_reels_timeout_to))
                        try:
                            client.media_like(reel.id)
                            logs['hashtags'][user]['reels_like'] += 1
                        except FeedbackRequired:
                            is_error_hashtags = True
                            errors['hashtags'][user]['reels_like'][reel.pk] = 'Too many requests, try later'
        progress_hashtags += 1
        set_progress(error_people=is_error_people, error_hashtags=is_error_hashtags, action_type=action,
                     people_processed=progress_people,
                     hashtags_processed=progress_hashtags)
        time.sleep(random.randint(hashtags_timeout_from, hashtags_timeout_to))

json_data = {
    'status': 'finished',
    'errors': json.dumps(errors),
    'output': json.dumps(logs)
}
requests.put(url, json=json_data)
