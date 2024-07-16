from ast import literal_eval

from instagrapi import Client

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
        client.user_follow(user_id)
    except Exception as e:
        errors[user] = str(e)
print(errors)