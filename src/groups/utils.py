import argparse

import aiohttp


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


async def is_valid_proxy(proxy: str):
    test_url: str = 'https://www.python.org/'

    async with aiohttp.ClientSession() as session:
        async with session.get(test_url, proxy=proxy) as response:
            if not response.headers.get('Via'):
                return False
            return True