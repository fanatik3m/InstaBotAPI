from ast import literal_eval

from instagrapi import Client
from instagrapi.exceptions import FeedbackRequired

client = Client()
settings = literal_eval(str(settings))
client.set_settings(settings)
if proxy is not None:
    client.set_proxy(f'socks5://{proxy}')
client.delay_range = [1, 5]

errors = {}
for hashtag in hashtags:
    posts = client.hashtag_medias_v1_chunk(hashtag, max_amount=20, tab_key='clips')[0]
    try:
        for post in posts:
            client.media_like(post.id)
    except FeedbackRequired:
        errors[hashtag] = 'Too many requests, try later'
print(errors)