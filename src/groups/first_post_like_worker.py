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
        last_post = client.user_medias(user_id, amount=1)[0]
    except PrivateError:
        errors[user_id] = 'Account is private'
    else:
        try:
            client.media_like(last_post.id)
        except FeedbackRequired:
            errors[user_id] = 'Too many requests, try later'
print(errors)