# import sys
# # import argparse
# from instagrapi import Client
#
# from ast import literal_eval
#
# # from utils import ParseKwargs
#
#
# def main():
#     # parser = argparse.ArgumentParser()
#     # parser.add_argument('-s', '--settings', nargs='*', action=ParseKwargs)
#     # parser.add_argument('-a', '--args', nargs='*')
#     # result = parser.parse_args()
#     # settings = result.settings
#     # args = result.args
#     #
#     # for key, value in settings.items():
#     #     if value.isdigit():
#     #         settings[key] = int(value)
#     #     elif value == 'None':
#     #         settings[key] = None
#     #     elif value == 'True':
#     #         settings[key] = True
#     #     elif value == 'False':
#     #         settings[key] = False
#     #
#     # args = [int(arg) if arg.isdigit() else arg for arg in args]
#
#     client = Client()
#     if settings:
#         settings = literal_eval(settings)
#         client.set_settings(settings)
#
#     func_to_execute = getattr(client, function_name)
#     return func_to_execute(*args)
#
#
# if __name__ == '__main__':
#     main()


from instagrapi import Client
from ast import literal_eval

client = Client()
settings = literal_eval(str(settings))
client.set_settings(settings)

func_to_execute = getattr(client, function_name)
result = func_to_execute(*args)
print(result)
