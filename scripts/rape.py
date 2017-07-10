import accounts
import vkapi
need_auth = True


def main(a, args):
    a.ignored_errors = {
        (15, 'messages.addChatUser'): ('Failed', False),
        (100, 'messages.addChatUser'): ('Failed', False),
        (10, 'messages.getLongPollServer'): ('Longpoll error', True),
    }
    if not args:
        print('Config file required')
        return
    data = open(accounts.abspath(args[0])).read().split()
    self_id = str(a.users.get()[0]['id'])
    print('My id:', self_id, flush=True)
    while True:
        lp = a.getLongpoll()
        for i in lp:
            if i[0] != 4:
                continue
            msg = vkapi.utils.LongpollMessage(i[1:])
            if msg.opt.get('source_act') == 'chat_kick_user' and msg.opt['source_mid'] in data and msg.opt['source_mid'] != self_id:
                print('Adding', msg.opt['source_mid'], flush=True)
                a.messages.addChatUser(user_id=msg.opt['source_mid'], chat_id=msg.sender - vkapi.CONF_START)
