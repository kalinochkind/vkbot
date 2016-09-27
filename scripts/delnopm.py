import logging
import scriptlib
import check_friend


# noinspection PyUnusedLocal
def main(a, args):
    friends = scriptlib.getFriends(a, fields='can_write_private_message')
    to_del = []
    for j in friends:
        if not j['can_write_private_message']:
            to_del.append(str(j['id']))
            logging.info('Found id{} ({} {})'.format(j['id'], j['first_name'], j['last_name']))
    check_friend.appendNoadd(to_del)
