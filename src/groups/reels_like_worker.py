from ast import literal_eval

from instagrapi import Client
from instagrapi.exceptions import PrivateError, FeedbackRequired

client = Client()
settings = literal_eval(str(settings))
client.set_settings(settings)
if proxy is not None:
    client.set_proxy(f'socks5://{proxy}')
client.delay_range = [timeout_from, timeout_to]

errors = {}
for user in users:
    try:
        user_id = client.user_info_by_username_v1(user).pk
        reels = client.user_clips(user_id, amount=amount)
    except PrivateError:
        errors[user] = 'Account is private'
    else:
        try:
            for reel in reels:
                client.media_like(reel.id)
        except FeedbackRequired:
            errors[user] = 'Too many requests, try later'
print(errors)