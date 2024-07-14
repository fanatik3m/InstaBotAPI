from ast import literal_eval

from instagrapi import Client

client = Client()
settings = literal_eval(str(settings))
client.set_settings(settings)
if proxy is not None:
    client.set_proxy(f'socks5://{proxy}')
client.delay_range = [1, 5]

result = {}
try:
    for user_id in users_ids:
        followers = client.user_followers(user_id, amount=amount)
        result[user_id] = list(followers.keys())
except Exception as e:
    callback = {
        'error': e,
        'parsed': result
    }
    print(callback)