import argparse
import re
import random
from typing import List
from enum import Enum

import requests


class ParseKwargs(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, dict())
        for value in values:
            key, value = value.split('=')
            getattr(namespace, self.dest)[key] = value


class Pagination:
    def __init__(self, page: int):
        self.limit: int = 10
        self.offset: int = self.limit * (page - 1)


def is_valid_proxy(proxy):
    proxies = {
        'https': f'socks5://{proxy}',
    }
    try:
        response = requests.get('https://www.python.org/', proxies=proxies)
        return True
    except:
        return False


def add_text_randomize(text: str) -> List[str]:
    strs = re.findall(r'\{([^}]+)\}', text)
    result_list = []
    for st in strs:
        res = re.sub(r"\((.*?)\)", lambda x: random.choice(x.group(1).split("|")), st)
        result_list.append(res)

    return result_list


class Status(Enum):
    working = 'working'
    stopped = 'stopped'
    paused = 'paused'
    finished = 'finished'


class ActionType(Enum):
    people = 'people'
    hashtag = 'hashtag'
    parse = 'parse'