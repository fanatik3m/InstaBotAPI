from ast import literal_eval

from instagrapi import Client

client = Client()
settings = literal_eval(str(settings))
client.set_settings(settings)
if proxy is not None:
    client.set_proxy(f'socks5://{proxy}')
client.delay_range = [1, 3]

result = {}
try:
    for user in users:
        user_id = client.user_info_by_username_v1(user).pk
        followers = client.user_followers(user_id, amount=amount)
        result[user] = [value.username for _, value in followers.items()]
except Exception as e:
    callback = {
        'error': str(e),
        'parsed': result
    }
    print(callback)
else:
    callback = {
        'error': None,
        'parsed': result
    }
    print(callback)