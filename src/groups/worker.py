from instagrapi import Client
from ast import literal_eval

client = Client()
settings = literal_eval(str(settings))
client.set_settings(settings)
if proxy is not None:
    client.set_proxy(proxy)

func_to_execute = getattr(client, function_name)
result = func_to_execute(*args)
print(result)
