from instagrapi import Client

from ast import literal_eval
client = Client()
settings = literal_eval(str(settings))
client.set_settings(settings)
if proxy is not None:
    client.set_proxy(f'socks5://{proxy}')
client.delay_range = [timeout_from, timeout_to]

liked_count = 0

try:
    for user in users:
        user_id = client.user_info_by_username_v1(user).pk
        stories = client.user_stories(user_id)
        for story in stories:
            client.story_like(story.id)
            liked_count += 1
except Exception as e:
    callback = {
        'liked': liked_count,
        'error': str(e)
    }
    print(callback)
else:
    callback = {
        'liked': liked_count,
        'error': None
    }
    print(callback)