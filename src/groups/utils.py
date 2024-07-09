import argparse


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