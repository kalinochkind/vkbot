#!/usr/bin/python3
import os
import sys

os.chdir(os.path.dirname(sys.argv[0]))

import accounts  # must be first
import log
import logging
import time
from vkbot import VkBot, CONF_START
import re
import check_friend
from calc import evalExpression
import random
import config
import signal
from server import MessageServer
import threading
from args import args
import stats

from prepare import login, password
from cppbot import CppBot  # should go after prepare import


def isBotMessage(msg, regex=re.compile(r'^\(.+\).')):
    return regex.match(msg.strip())


bot = CppBot()

noans = open(accounts.getFile('noans.txt'), encoding='utf-8').read().splitlines()
smiles = open(accounts.getFile('smiles.txt'), encoding='utf-8').read().splitlines()
random.shuffle(noans)


class BanManager:
    def __init__(self, filename):
        self.filename = filename
        self.banned = set(map(int, open(filename).read().split()))

    def write(self):
        s = list(map(str, sorted(self.banned)))
        with open(self.filename, 'w') as f:
            f.write('\n'.join(s))

    def ban(self, pid):
        if pid in self.banned:
            return False
        self.banned.add(pid)
        self.write()
        return True

    def unban(self, pid):
        if pid not in self.banned:
            return False
        self.banned.discard(pid)
        self.write()
        return True


# noinspection PyDefaultArgument
def timeto(name, interval, d={}):
    if interval >= 0 and time.time() > d.get(name, 0) + interval:
        d[name] = time.time()
        return True
    return False


def renderSmile(s, regex=re.compile(r'&#(\d+);')):
    return regex.sub(lambda x: chr(int(x.group(1))), s)


last_reply_lower = set()
_cmd_re = re.compile(r'\\[a-zA-Z]+')


# conf_id == -1: comment
# conf_id == -2: flat
def getBotReply(uid, message, conf_id, method='', onsend_actions=None):
    if message is None:
        return ''  # if we return None, markAsRead is done immediately

    message = message.replace('\u0401', '\u0415').replace('\u0451', '\u0435')  # yo
    message = message.replace('\u0490', '\u0413').replace('\u0491', '\u0433')  # g
    message = message.replace('\u0404', '\u042d').replace('\u0454', '\u044d')  # e
    message = message.replace('\u0406', '\u0418').replace('\u0456', '\u0438')  # i
    message = message.replace('\u0407', '\u0418').replace('\u0457', '\u0438')  # i
    message = message.replace("`", "'")

    if conf_id == 0:
        answer = bot.interact('user {} {}'.format(uid, message))
    elif conf_id in (-1, -2):
        answer = bot.interact('{} {}'.format('comm' if conf_id == -1 else 'flat 0', message))
        bl = (answer == '$blacklisted')
        return bl
    else:
        answer = bot.interact('conf {} {}'.format(uid, message))

    if answer == '$noans':
        if message.upper() == message.lower() and '?' not in message:
            answer = random.choice(smiles)
        else:
            answer = noans[0]
            next_ans = random.randint(1, len(noans) - 1)
            noans[0], noans[next_ans] = noans[next_ans], noans[0]
    elif answer == '$blacklisted':
        answer = ''

    if message == message.lower() and message != message.upper() or message.upper() == message.lower() and uid in last_reply_lower:
        last_reply_lower.add(uid)
        answer = answer.lower()
    else:
        last_reply_lower.discard(uid)
    console_message = ''

    if '{' in answer:
        answer, gender = applyGender(answer, uid)
        console_message += ' (' + gender + ')'

    if '\\' in answer:
        res = _cmd_re.sub(lambda m: preprocessReply(m.group(0)[1:], uid, onsend_actions), answer)
        console_message += ' (' + answer + ')'
        answer = res

    if method:
        console_message += ' (' + method + ')'
    text_msg = '({}) {} : {}{}'.format(vk.printableSender({'user_id': uid, 'chat_id': conf_id}, False), message, renderSmile(answer), console_message)
    html_msg = '({}) {} : {}{}'.format(vk.printableSender({'user_id': uid, 'chat_id': conf_id}, True), message, renderSmile(answer).replace('&', '&amp;'), console_message)
    logging.info(text_msg, extra={'db': html_msg})
    return answer


bot_users = {}


# returns (text, is_friendship_request)
# for friendship requests we do not call markAsRead
# None: just ignore the message
# (None, False): immediate MarkAsRead
def reply(message):
    if vk.getSender(message) in banign.banned:
        vk.banned_list.append(vk.getSender(message))
        return None
    if vk.getSender(message) < 0:
        return None
    if vk.getSender(message) in check_friend.noadd or message['user_id'] in check_friend.noadd:
        return (None, False)
    if 'deactivated' in vk.users[message['user_id']] or vk.users[message['user_id']]['blacklisted'] or vk.users[message['user_id']]['blacklisted_by_me']:
        return (None, False)

    if 'body' not in message:
        message['body'] = ''

    onsend_actions = []

    if 'id' not in message:  # friendship request
        return (getBotReply(message['user_id'], message['message'], 0, 'friendship request', onsend_actions), True)

    if isBotMessage(message['body']):
        vk.logSender('(%sender%) {} - ignored (bot message)'.format(message['body']), message)
        if 'chat_id' in message:
            bot_users[message['user_id']] = bot_users.get(message['user_id'], 0) + 1
            if bot_users[message['user_id']] >= 3:
                logging.info('Too many bot messages')
                log.write('conf', str(message['user_id']) + ' ' + str(message['chat_id']) + ' (bot messages)')
                vk.leaveConf(message['chat_id'])
        return ('', False)
    elif message['user_id'] in bot_users:
        del bot_users[message['user_id']]

    message['body'] = preprocessMessage(message)

    if message['body']:
        user_msg = vk.last_message.byUser(message['user_id'])
        if message['body'] == user_msg.get('text') and message['body'] != '..':
            user_msg['count'] = user_msg.get('count', 0) + 1  # this modifies the cache entry too
            if user_msg['count'] >= 5:
                noaddUsers([message['user_id']], reason='flood')
            else:
                vk.logSender('(%sender%) {} - ignored (repeated)'.format(message['body']), message)
            return ('', False)

        if 'reply' in user_msg and message['body'].upper() == user_msg['reply'].upper():
            vk.logSender('(%sender%) {} - ignored (my reply)'.format(message['body']), message)
            user_msg['text'] = user_msg['reply']  # this modifies the cache entry too
            # user_msg['count'] = 1  # do we need it?
            return ('', False)

        t = evalExpression(message['body'])
        if t:
            if getBotReply(None, message['body'], -2):
                return ('', False)
            vk.logSender('(%sender%) {} = {} (calculated)'.format(message['body'], t), message)
            log.write('calc', '{}: "{}" = {}'.format(vk.loggableName(message['user_id']), message['body'], t))
            return (t, False)
        tbody = message['body'].replace('<br>', '')
        if tbody.upper() == tbody and sum(i.isalpha() for i in tbody) > 1:
            vk.logSender('(%sender%) {} - ignored (caps)'.format(message['body']), message)
            return ('', False)

    bot_reply = getBotReply(message['user_id'], message['body'], message.get('chat_id', 0), message.get('_method', ''), onsend_actions)
    message['_onsend_actions'] = onsend_actions
    return (bot_reply, False)


def preprocessMessage(message):
    if message.get('user_id') == vk.self_id:
        return ''

    if 'action' in message:
        return None

    result = message['body']
    att = []
    for a in message.get('attachments', []):
        if a['type'] == 'audio':
            att.append(a['audio']['title'])
        elif a['type'] == 'video':
            att.append(a['video']['title'])
        elif a['type'] == 'wall':
            att.append(a['wall']['text'])
            if not a['wall']['text'] and 'copy_history' in a['wall']:
                att[-1] = a['wall']['copy_history'][0]['text']
        elif a['type'] == 'doc':
            if a['doc']['type'] == 5:  # voice message
                result += ' [Voice]'
            else:
                att.append(a['doc']['title'])
        elif a['type'] == 'gift':
            att.append('vkgift')
        elif a['type'] == 'link':
            att.append(a['link']['description'])
        elif a['type'] == 'market':
            att.append(a['market']['description'])
        elif a['type'] == 'sticker':
            return None
        elif a['type'] == 'photo':
            result += ' ..'
    for a in att:
        result += ' [' + a.lower() + ']'
    result = result.replace('vkgift', 'Vkgift')

    if 'fwd_messages' in message:
        fwd_users = {fwd['user_id'] for fwd in message['fwd_messages']}
        if fwd_users in ({vk.self_id}, {message['user_id'], vk.self_id}):
            return result.strip() or None
        elif fwd_users == {message['user_id']}:
            for fwd in message['fwd_messages']:
                r = preprocessMessage(fwd)
                if r is None:
                    return None
                result += ' {' + str(r) + '}'
        else:
            return None

    return result.strip()


def preprocessReply(s, uid, onsend_actions):
    if s == 'myname':
        return vk.users[uid]['first_name']
    if s == 'mylastname':
        return vk.users[uid]['last_name']
    if s == 'curtime':
        return time.strftime("%H:%M", time.localtime())
    if s == 'likeava':
        onsend_actions.append(lambda: vk.likeAva(uid))
        return ''
    if s == 'gosp':
        onsend_actions.append(lambda: vk.setRelation(uid))
        return ''
    if s == 'phone':
        return vk.phone
    if s == 'age':
        return str(vk.age)
    if s == 'name':
        return vk.name[0]
    if s == 'lastname':
        return vk.name[1]
    if s == 'bf':
        if vk.bf:
            return 'https://vk.com/id' + str(vk.bf['id'])
        else:
            return ''
    if s == 'bfname':
        if vk.bf:
            return vk.bf['first_name']
        else:
            return ''
    if s == 'bflastname':
        if vk.bf:
            return vk.bf['last_name']
        else:
            return ''
    logging.error('Unknown variable: ' + s)


# 1: female, 2: male
def applyGender(msg, uid, male_re=re.compile(r'\{m([^\{\}]*)\}'), female_re=re.compile(r'\{f([^\{\}]*)\}')):
    gender = ['male', 'female', 'male'][vk.users[uid]['sex']]
    if gender == 'female':
        msg = male_re.sub('', msg)
        msg = female_re.sub('\\1', msg)
    else:
        msg = female_re.sub('', msg)
        msg = male_re.sub('\\1', msg)
    return msg, gender


def testFriend(uid, need_reason=False):
    fr = vk.users[uid]
    if fr is None:
        return False
    return check_friend.isGood(fr, need_reason)


def noaddUsers(users, remove=False, reason=None, lock=threading.Lock()):
    if config.get('vkbot.no_ignore'):
        return 0
    users = set(users)
    if not users:
        return 0
    with lock:
        if remove:
            prev_len = len(check_friend.noadd)
            check_friend.noadd -= users
            check_friend.writeNoadd()
            return prev_len - len(check_friend.noadd)
        else:
            users -= check_friend.noadd
            users.discard(vk.admin)
            if not users:
                return 0
            text_msg = 'Deleting ' + ', '.join([vk.printableSender({'user_id': i}, False) for i in users]) + (' ({})'.format(reason) if reason else '')
            html_msg = 'Deleting ' + ', '.join([vk.printableSender({'user_id': i}, True) for i in users]) + (' ({})'.format(reason) if reason else '')
            logging.info(text_msg, extra={'db': html_msg})
            check_friend.appendNoadd(users)
            vk.deleteFriend(users)
            return len(users)


# noinspection PyUnusedLocal
def reloadHandler(*p):
    bot.interact('reld')
    vk.initSelf()
    logging.info('Reloaded!')
    return 'Reloaded!'


# noinspection PyUnusedLocal
def onExit(*p):
    logging.info('Received SIGTERM')
    loop_thread.join(60)
    vk.waitAllThreads()
    logging.info('Bye')
    logging.shutdown()
    sys.exit()


signal.signal(signal.SIGTERM, onExit)

vk = VkBot(login, password)
vk.admin = config.get('vkbot.admin', 'i')
vk.bad_conf_title = lambda s: getBotReply(None, ' ' + s, -2)
logging.info('My id: ' + str(vk.self_id))
banign = BanManager(accounts.getFile('banned.txt'))
vk.banned = banign.banned
if args['whitelist']:
    vk.whitelist = [vk.getUserId(i) or i for i in args['whitelist'].split(',')]
    logging.info('Whitelist: ' + ', '.join(map(lambda x: x if isinstance(x, str) else vk.printableName(x, user_fmt='{name}'), vk.whitelist)))

addfriends_interval = config.get('intervals.addfriends', 'i')
includeread_interval = config.get('intervals.includeread', 'i')
setonline_interval = config.get('intervals.setonline', 'i')
unfollow_interval = config.get('intervals.unfollow', 'i')
filtercomments_interval = config.get('intervals.filtercomments', 'i')
stats_interval = config.get('intervals.stats', 'i')
groupinvites_interval = config.get('intervals.groupinvites', 'i')


def ignoreHandler(user):
    user = vk.getUserId(user)
    if not user:
        return 'Invalid user'
    if noaddUsers([user], reason='external command'):
        return 'Ignored ' + vk.printableName(user, user_fmt='{name}')
    else:
        return vk.printableName(user, user_fmt='{name}') + ' already ignored'


def unignoreHandler(user):
    user = vk.getUserId(user)
    if not user:
        return 'Invalid user'
    if noaddUsers([user], True):
        return 'Unignored ' + vk.printableName(user, user_fmt='{name}')
    else:
        if banign.unban(user):
            return 'Unbanned ' + vk.printableName(user, user_fmt='{name}')
        return vk.printableName(user, user_fmt='{name}') + ' is not ignored'


def banHandler(user):
    user = vk.getUserId(user)
    if not user:
        return 'Invalid user'
    return ('Banned {}' if banign.ban(user) else '{} already banned').format(vk.printableName(user, user_fmt='{name}'))


def unbanHandler(user):
    user = vk.getUserId(user)
    if not user:
        return 'Invalid user'
    return ('Unbanned {}' if banign.unban(user) else '{} is not banned').format(vk.printableName(user, user_fmt='{name}'))


def isignoredHandler(user):
    user = vk.getUserId(user)
    if user is None or user > CONF_START:
        return 'Invalid user'
    r = testFriend(user, True)
    if r is None:
        return 'Good'
    return r


def leaveHandler(conf):
    conf = vk.getUserId(conf)
    if conf > CONF_START:
        conf -= CONF_START
    if vk.leaveConf(conf):
        return 'Ok'
    else:
        return 'Fail'


# noinspection PyUnusedLocal
def banlistHandler(*p):
    if banign.banned:
        result = sorted(banign.banned)
        result = [vk.printableName(j, user_fmt='<a href="https://vk.com/id{id}">{name}</a><br>') for j in result]
        return '\n'.join(result)
    else:
        return 'No one banned!'


if config.get('server.port', 'i') > 0:
    srv = MessageServer()
    srv.addHandler('reply', lambda x: bot.interact('flat ' + x, False))
    srv.addHandler('stem', lambda x: bot.interact('stem ' + x, False))
    srv.addHandler('ignore', ignoreHandler)
    srv.addHandler('unignore', unignoreHandler)
    srv.addHandler('ban', banHandler)
    srv.addHandler('unban', unbanHandler)
    srv.addHandler('reload', reloadHandler)
    srv.addHandler('isignored', isignoredHandler)
    srv.addHandler('leave', leaveHandler)
    srv.addHandler('banlist', banlistHandler)
    srv.listen()
    logging.info('Running TCP server on port ' + config.get('server.port'))

check_friend.writeNoadd()
stats.update('started', time.time())


def main_loop():
    try:
        if timeto('setonline', setonline_interval):
            vk.setOnline()
        if timeto('filtercomments', filtercomments_interval):
            noaddUsers(vk.filterComments(lambda s: getBotReply(None, s, -1)), reason='bad comment')
            stats.update('blacklisted', vk.blacklistedCount())
        if timeto('unfollow', unfollow_interval):
            noaddUsers(vk.unfollow(), reason='deleted me')
        if timeto('addfriends', addfriends_interval):
            vk.addFriends(reply, testFriend)
        if includeread_interval >= 0:
            vk.replyAll(reply, timeto('includeread', includeread_interval))
        else:
            time.sleep(1)
        if timeto('stats', stats_interval):
            vk.initSelf(True)
            count, dialogs, confs = vk.lastDialogs()
            if count is not None:
                vk.loadUsers(dialogs, lambda x: x[0])
                dialogs = [[uid, vk.printableName(uid, '{name}', conf_fmt='Conf "%s"' % confs.get(uid).replace('{', '{{').replace('}', '}}')), cnt] for uid, cnt in dialogs if
                           uid > 0]
                stats.update('dialogs', count)
                stats.update('dialogs_list', dialogs)
                stats.update('phone', vk.phone)
                stats.update('bf', vk.printableSender({'user_id': vk.bf['id']}, True))
        if timeto('groupinvites', groupinvites_interval):
            vk.acceptGroupInvites()
    except Exception as e:
        logging.exception('global {}: {}'.format(e.__class__.__name__, str(e)))
        time.sleep(2)


while True:
    loop_thread = threading.Thread(target=main_loop)
    loop_thread.start()
    loop_thread.join()
