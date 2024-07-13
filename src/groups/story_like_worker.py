from instagrapi import Client

from ast import literal_eval
client = Client()
settings = literal_eval(str(settings))
client.set_settings(settings)
if proxy is not None:
    client.set_proxy(f'socks5://{proxy}')
client.delay_range = [1, 5]

liked_count = 0

for user_id in users_ids:
    stories = client.user_stories(user_id)
    for story in stories:
        client.story_like(story.id)
        liked_count += 1
print(liked_count)