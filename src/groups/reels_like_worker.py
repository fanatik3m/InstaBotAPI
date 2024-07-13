from ast import literal_eval

from instagrapi import Client
from instagrapi.exceptions import PrivateError, FeedbackRequired

client = Client()
settings = literal_eval(str(settings))
client.set_settings(settings)
if proxy is not None:
    client.set_proxy(f'socks5://{proxy}')
client.delay_range = [1, 5]

errors = {}
for user_id in users_ids:
    try:
        reels = client.user_clips(user_id, amount=amount)
    except PrivateError:
        errors[user_id] = 'Account is private'
    else:
        try:
            for reel in reels:
                client.media_like(reel.id)
        except FeedbackRequired:
            errors[user_id] = 'Too many requests, try later'
print(errors)