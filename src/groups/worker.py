import sys
from instagrapi import Client


def main():
    func_name, func_args, settings = sys.argv[1:4]
    client = Client()
    if settings:
        client.set_settings(settings)

    func_to_execute = getattr(client, func_name)
    return func_to_execute(*func_args)


if __name__ == '__main__':
    main()