#!/usr/bin/python3

import log  # must be first
import time
import sys
from vkbot import vk_bot, CONF_START
import vkapi
import re
import check_friend
from calc import evalExpression
import config
from cppbot import cpp_bot
import signal
import os
import codecs
import fcntl
from server import MessageServer

pid_file = 'inf.pid'
fp = open(pid_file, 'w')
single = 0
for i in range(100):
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        time.sleep(5)
    else:
        single = 1
        break
if not single:
    sys.exit(0)

log.info('Starting vkbot')
os.environ['LC_ALL'] = 'ru_RU.utf-8'
sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

_bot_message = re.compile(r'^\(.+\)')
def isBotMessage(msg):
    return _bot_message.match(msg.strip())

bot_users = {}

bot = cpp_bot()

class ban_manager:
    def __init__(self, filename, user_cache):
        self.filename = filename
        self.users = user_cache
        banign = open(filename).read().split()
        self.banned = set(map(int, banign))

    def write(self):
        s = list(map(str, sorted(self.banned)))
        with open(self.filename, 'w') as f:
            f.write('\n'.join(s))

    # {name} - first_name last_name
    # {id} - id
    def printableName(self, pid, user_fmt = '<a href="https://vk.com/id{id}" target="_blank">{name}</a>', conf_fmt = 'Conf {id}'):
        if pid > CONF_START:
            return conf_fmt.format(id=(pid - CONF_START))
        else:
            return user_fmt.format(id=(pid), name=self.users[pid]['first_name'] + ' ' + self.users[pid]['last_name'])

    def ban(self, pid):
        if pid in self.banned:
            return 'Already banned!'
        self.banned.add(pid)
        self.write()
        return self.printableName(pid, user_fmt='[id{id}|{name}]') + ' banned'

    def unban(self, pid):
        if pid not in self.banned:
            return 'Not banned!'
        else:
            self.banned.discard(pid)
            self.write()
            return self.printableName(pid, user_fmt='[id{id}|{name}]') + ' unbanned'


_timeto = {}
def timeto(name, interval):
    if time.time() > _timeto.get(name, 0) + interval:
        _timeto[name] = time.time()
        return 1
    return 0


# conf_id == -1: comment
def getBotReply(uid, message, conf_id, method=''):
    if message is None:
        return None

    message = message.replace('\u0401', '\u0415').replace('\u0451', '\u0435')  # yo
    message = message.replace('\u0490', '\u0413').replace('\u0491', '\u0433')  # g
    message = message.replace('\u0404', '\u042d').replace('\u0454', '\u044d')  # e
    message = message.replace('\u0406', '\u0418').replace('\u0456', '\u0438')  # i
    message = message.replace('\u0407', '\u0418').replace('\u0457', '\u0438')  # i

    if conf_id == 0:
        answer = bot.interact('user {} {}'.format(uid, message))
    elif conf_id > 0:
        answer = bot.interact('conf {} {}'.format(uid, message))
    elif conf_id == -1:
        answer = bot.interact('flat {}'.format(message))
        bl = (answer == '$blacklisted')
        return bl

    if message == message.lower() and message != message.upper():
        answer = answer.lower()
    console_message = ''

    if '{' in answer:
        answer, gender = applyGender(answer, uid)
        console_message += ' (' + gender + ')'

    if answer.startswith('\\'):
        res = preprocessReply(answer[1:], uid)
        log.write('preprocess', '{}: {} ({} -> {})'.format(uid, answer, message, res))
        if res is None:
            log.error('Unknown reply:', answer)
            res = ''
        console_message += ' (' + answer + ')'
        answer = res

    if method:
        console_message += ' (' + method + ')'
    if conf_id > 0:
        log.info('({}) {} : {}{}'.format(banign.printableName(uid, user_fmt='Conf %c, <a href="https://vk.com/id{id}" target="_blank">{name}</a>').replace('%c', str(conf_id)), message, answer, console_message))
    else:
        log.info('({}) {} : {}{}'.format(banign.printableName(uid), message, answer, console_message))
    return answer

def processCommand(cmd, *p):
    if cmd == 'reload':
        bot.interact('reld')
        vk.initSelf()
        log.info('Reloaded!')
        return 'Reloaded!'

    elif cmd == 'banned':
        if banign.banned:
            result = sorted(banign.banned)
            result = [banign.printableName(j, user_fmt='[id{id}|{name}]') for j in result]
            return '\n'.join(result)
        else:
            return 'No one banned!'

    elif cmd == 'ban':
        if not p:
            return 'Not enough parameters'
        user = vk.getUserId(p[-1])
        if user is None:
            return 'No such user'
        if user == admin:
            return 'Cannot ban admin!'
        return banign.ban(user)

    elif cmd == 'unban':
        if not p:
            return 'Not enough parameters'
        user = p[-1]
        if user != '*':
            user = vk.getUserId(user)
        return banign.unban(user)

    elif cmd == 'ignore':
        users = vk.getUserId(p)
        if not users:
            return 'No such users'
        if admin in users:
            return 'Cannot ignore admin!'
        noaddUsers(users)
        vk.users.load(users)
        return 'Ignored ' +  ', '.join(banign.printableName(i, user_fmt='[id{id}|{name}]') for i in users)

    elif cmd == 'unignore':
        users = vk.getUserId(p)
        if not users:
            return 'No such users'
        if admin in users:
            return 'Cannot ignore admin!'
        noaddUsers(users, True)
        vk.users.load(users)
        return 'Unignored ' +  ', '.join(banign.printableName(i, user_fmt='[id{id}|{name}]') for i in users)

    elif cmd == 'leave':
        if not p:
            return 'Not enough parameters'
        if not p[-1].isdigit():
            return 'Invalid conf id'
        cid = int(p[-1])
        if vk.leaveConf(cid):
            return 'Ok'
        else:
            return 'Fail'

    else:
        return 'Unknown command'


# returns (text, mode)
# mode=0: default, mode=1: no delay, mode=2: friendship request
def reply(message):
    if vk.getSender(message) in banign.banned:
        return None
    if vk.getSender(message) < 0:
        return None
    if vk.getSender(message) in check_friend.noadd or message['user_id'] in check_friend.noadd:
        return ('', 0)
    if 'deactivated' in vk.users[message['user_id']] or vk.users[message['user_id']]['blacklisted'] or vk.users[message['user_id']]['blacklisted_by_me']:
        return ('', 0)

    if 'body' not in message:
        message['body'] = ''

    if 'id' not in message:  # friendship request
        return (getBotReply(message['user_id'], message['message'], 0), 2)
    message['body'] = preprocessMessage(message)

    if message['body']:
        if message['body'].startswith('\\') and len(message['body']) > 1:
            cmd = message['body'][1:].split()
            if cmd:
                if reset_command and cmd[0] == reset_command:
                    cmd = cmd[1:]
                    vk.sendMessage(admin, '{} from {}'.format(cmd, message['user_id']))
                    return (processCommand(*cmd), 1)
                elif message['user_id'] == admin:
                    return (processCommand(*cmd), 1)

        if isBotMessage(message['body']):
            log.info('({}) {} - ignored (bot message)'.format(banign.printableName(message['user_id']), message['body']))
            if 'chat_id' in message:
                bot_users[message['user_id']] = bot_users.get(message['user_id'], 0) + 1
                if bot_users[message['user_id']] >= 3:
                    log.info('Too many bot messages')
                    log.write('conf', str(message['user_id']) + ' ' + str(message['chat_id']) + ' (bot messages)')
                    vk.leaveConf(message['chat_id'])
            return ('', 0)
        elif message['user_id'] in bot_users:
            del bot_users[message['user_id']]

        if message['body'].strip().upper() == last_message_text.get(vk.getSender(message)):
            log.info('({}) {} - ignored (my reply)'.format(banign.printableName(message['user_id']), message['body']))
            return ('', 0)

        t = evalExpression(message['body'])
        if t:
            if getBotReply(None, message['body'], -1):
                return ('', 0)
            if 'chat_id' in message:
                log.info('({}) {} = {} (calculated)'.format(banign.printableName(message['user_id'], user_fmt='Conf %c, {name}').replace('%c', str(message['chat_id'])), message['body'], t))
            else:
                log.info('({}) {} = {} (calculated)'.format(banign.printableName(message['user_id']), message['body'], t))
            log.write('calc', '{}: "{}" = {}'.format(message['user_id'], message['body'], t))
            return (t, 0)
    if message['body']:
        message['body'] = message['body'].replace('<br>', '<BR>')
    if message['body'] and message['body'].upper() == message['body'] and len([i for i in message['body'] if i.isalpha()]) > 1:
        if 'chat_id' in message:
            log.info('({}) {} - ignored (caps)'.format(banign.printableName(message['user_id'], user_fmt='Conf %c, {name}').replace('%c', str(message['chat_id'])), message['body']))
        else:
            log.info('({}) {} - ignored (caps)'.format(banign.printableName(message['user_id']), message['body']))
        return ('', 0)

    reply = getBotReply(message['user_id'], message['body'] , message.get('chat_id', 0), message.get('_method', ''))
    if reply is not None:
        last_message_text[vk.getSender(message)] = reply.strip().upper()
    return (reply, 0)


def preprocessMessage(message, user=None):
    if user is not None and message.get('user_id') != user:
        return None

    if 'action' in message:
        if message['action'] == 'chat_invite_user' and message['action_mid'] == vk.self_id:
            vk.deleteFriend(message['user_id'])
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
        elif a['type'] == 'doc':
            att.append(a['doc']['title'])
        elif a['type'] == 'gift':
            att.append('vkgift')
        elif a['type'] == 'link':
            att.append(a['link']['description'])
        elif a['type'] == 'sticker':
            return None
    for a in att:
        result += ' [' + a.lower() + ']'
    result = result.replace('vkgift', 'Vkgift')

    for fwd in message.get('fwd_messages', []):
        if len(message['fwd_messages']) == 1 and fwd.get('user_id') == vk.self_id and result:
            continue
        r = preprocessMessage(fwd, message.get('user_id'))
        if r is None:
            return None
        result  += ' {' + str(r) + '}'

    if user is None and 'attachments' not in message and not result:
        return None
    return result.strip()


def preprocessReply(s, uid):
    if s == 'myname':
        return vk.users[uid]['first_name']
    if s == 'mylastname':
        return vk.users[uid]['last_name']
    if s == 'curtime':
        return time.strftime("%H:%M", time.localtime())
    if s.startswith('likeava'):
        vk.likeAva(uid)
        return s.split(maxsplit=1)[1]
    if s.startswith('gosp'):
        vk.setRelation(uid)
        return s.split(maxsplit=1)[1]
    if s == 'phone':
        return vk.phone


_male_re = re.compile(r'\{m([^\{\}]*)\}')
_female_re = re.compile(r'\{f([^\{\}]*)\}')

# 1: female, 2: male
def applyGender(msg, uid):
    gender = ['male', 'female', 'male'][vk.users[uid]['sex']]
    if gender == 'female':
        msg = _male_re.sub('', msg)
        msg = _female_re.sub('\\1', msg)
    else:
        msg = _female_re.sub('', msg)
        msg = _male_re.sub('\\1', msg)
    return msg, gender

def test_friend(uid):
    try:
        fr = vk.api.users.get(user_ids=uid, fields=check_friend.fields)[0]
    except KeyError:
        return 0
    return check_friend.is_good(fr)

def noaddUsers(users, remove=False):
    users = set(users)
    users.discard(admin)
    if not users:
        return
    if remove:
        check_friend.noadd -= users
    else:
        check_friend.noadd.update(users)
        log.info('Deleting ' + ', '.join([banign.printableName(i) for i in users]))
        vk.deleteFriend(users)
    check_friend.writeNoadd()

def _onexit(*p):
    log.info('Received SIGTERM')
    vk.waitAllThreads()
    log.info('Bye')
    exit(0)

signal.signal(signal.SIGTERM, _onexit)

if sys.argv[-1] == '-l':
    vkapi.vk_api.logging = 1
    log.info('Logging enabled')

cfg = list(map(str.strip, open('data.txt').read().strip().splitlines()))
admin = int(cfg[2]) if len(cfg) > 2 else -1
reset_command = cfg[3] if len(cfg) > 3 else ''
last_message_text = {}

vk = vk_bot(cfg[0], cfg[1]) # login, pass
log.info('My id: ' + str(vk.self_id))

banign = ban_manager('banned.txt', vk.users)

addfriends_interval = config.get('inf.addfriends_interval')
includeread_interval = config.get('inf.includeread_interval')
setonline_interval = config.get('inf.setonline_interval')
unfollow_interval = config.get('inf.unfollow_interval')
filtercomments_interval = config.get('inf.filtercomments_interval')

srv = MessageServer()
srv.addHandler('reply', lambda x:bot.interact('flat ' + x))
srv.listen()

reply_all = False
while 1:
    try:
        vk.replyAll(reply, reply_all)
        reply_all = vk.api.captchaError
        vk.api.captchaError = False
        if timeto('addfriends', addfriends_interval):
            vk.addFriends(reply, test_friend)
        if timeto('includeread', includeread_interval):
            reply_all = True
        if timeto('setonline', setonline_interval):
            vk.setOnline()
        if timeto('unfollow', unfollow_interval):
            noaddUsers(vk.unfollow(banign.banned))
        if timeto('filtercomments', filtercomments_interval):
            noaddUsers(vk.filterComments(lambda s:getBotReply(None, s, -1), banign.printableName))
    except Exception as e:
        log.error('global {}: {}'.format(e.__class__.__name__, str(e)), True)
        reply_all = True
        time.sleep(2)
