import time
from ast import literal_eval
import re
import random
from datetime import datetime, timedelta

from instagrapi import Client

client = Client()
settings = literal_eval(str(settings))
client.set_settings(settings)
if proxy is not None:
    client.set_proxy(proxy)

client.delay_range = [1, 3]

no_dialogs_in = timedelta(**no_dialogs_in)


def text_randomize(text: str):
    strs = re.findall(r'\{([^}]+)\}', text)
    result_list = []
    for st in strs:
        res = re.sub(r"\((.*?)\)", lambda x: random.choice(x.group(1).split("|")), st)
        result_list.append(res)

    return result_list


while True:
    time.sleep(random.randint(120, 180))
    threads = client.direct_threads(amount=0, thread_message_limit=1)
    for thread in threads:
        last_message_time = thread.messages[0].timestamp
        time_diff = datetime.now() - last_message_time
        if time_diff > no_dialogs_in:
            for message in text_randomize(text):
                client.direct_answer(thread.id, message)

    # for follower_id in followers_ids:
    #     thread = client.direct_thread_by_participants([follower_id])
    #     if thread.get('thread'):
    #         items = thread.get('thread').get('items')
    #         if items:
    #             item = items[0]
    #             last_message_time = datetime.fromtimestamp(item.get('timestamp') / 1000000)
    #             time_diff = datetime.now() - last_message_time
    #             if time_diff > no_dialogs_in:
    #                 for message in text_randomize(text):
    #                     client.direct_send(message, user_ids=[follower_id])
    #         else:
    #             for message in text_randomize(text):
    #                 client.direct_send(message, user_ids=[follower_id])