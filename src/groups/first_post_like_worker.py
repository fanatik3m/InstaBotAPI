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
        last_post = client.user_medias(user_id, amount=1)[0]
    except PrivateError:
        errors[user] = 'Account is private'
    else:
        try:
            client.media_like(last_post.id)
        except FeedbackRequired:
            errors[user] = 'Too many requests, try later'
print(errors)