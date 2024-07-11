import time
from ast import literal_eval
import re
import random
from datetime import datetime

from instagrapi import Client

client = Client()
settings = literal_eval(str(settings))
client.set_settings(settings)
if proxy is not None:
    client.set_proxy(proxy)

self_user_id = client.account_info().pk


def text_randomize(text: str):
    strs = re.findall(r'\{([^}]+)\}', text)
    result_list = []
    for st in strs:
        res = re.sub(r"\((.*?)\)", lambda x: random.choice(x.group(1).split("|")), st)
        result_list.append(res)

    return result_list


while True:
    time.sleep(300)
    followers = client.user_followers(self_user_id)
    followers_ids = list(followers.keys())
    threads = client.direct_thread_by_participants(followers_ids)
    items = threads.get('thread').get('items')

    worked_ids = []
    result_items = []
    for item in items:
        if item.get('user_id') in worked_ids:
            continue
        worked_ids.append(item.get('user_id'))
        result_items.append(item)

    for item in result_items:
        last_message_time = datetime.fromtimestamp(item.get('timestamp') / 1000000)
        time_diff = datetime.now() - last_message_time
        if time_diff > no_dialogs_in:
            for message in text_randomize(text):
                client.direct_send(message, user_ids=[item.get('user_id')])
