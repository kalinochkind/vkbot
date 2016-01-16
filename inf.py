#!/usr/bin/python3

import time
import sys
from subprocess import Popen, PIPE
from vkbot import vk_bot
import vkapi
import captcha
import re
import check_friend
from calc import evalExpression
import log
import config


_bot_message = re.compile(r'^\(.+\)')
def isBotMessage(msg):
    return _bot_message.match(msg.strip())


class cpp_bot:
    def __init__(self, filename):
        self.bot = Popen([filename], stdout=PIPE, stdin=PIPE)

    def interact(self, msg):
        self.bot.stdin.write(msg.replace('\n', '\a').strip().encode() + b'\n')
        self.bot.stdin.flush()
        answer = self.bot.stdout.readline().rstrip().replace(b'\a', b'\n')
        return answer.decode().strip()

bot = cpp_bot('./chat.exe')


class ban_manager:
    def __init__(self, filename):
        self.filename = filename
        banign = open(filename).read().split()
        self.banned = set(i[1:] for i in banign if i.startswith('$'))
        self.ignored = set(i for i in banign if not i.startswith('$'))

    def write(self):
        s = ['$' + i for i in sorted(self.banned, key=int)] + sorted(self.ignored, key=int)
        with open(self.filename, 'w') as f:
            f.write('\n'.join(s))

    def printableName(self, pid):
        pid = int(pid)
        if pid > 2000000000:
            return 'Conf ' + str(pid - 2000000000)
        else:
            return 'User ' + str(pid)

    def ban(self, pid):
        pid = str(pid)
        if pid in self.banned:
            return 'Already banned!'
        self.banned.add(pid)
        self.write()
        return self.printableName(pid) + ' banned'

    def ignore(self, pid):
        pid = str(pid)
        if pid in self.ignored:
            return 'Already ignored!'
        self.ignored.add(pid)
        self.write()
        return self.printableName(pid) + 'ignored'

    def unban(self, pid):
        pid = str(pid)
        if pid == '*':
            ret = '{} unbanned'.format(', '.join(self.banned))
            self.banned = set()
        elif pid not in self.banned:
            return 'Not banned!'
        else:
            self.banned.discard(pid)
            ret = self.printableName(pid) + ' unbanned'
        self.write()
        return ret

    def unban(self, pid):
        pid = str(pid)
        if pid == '*':
            ret = '{} unignored'.format(', '.join(self.ignored))
            self.ignored = set()
        elif pid not in self.ignored:
            return 'Not ignored!'
        else:
            self.ignored.discard(pid)
            ret = self.printableName(pid) + ' unignored'
        self.write()
        return ret

banign = ban_manager('banned.txt')


_timeto = {}
def timeto(name, interval):
    if time.time() > _timeto.get(name, 0) + interval:
        _timeto[name] = time.time()
        return 1
    return 0


def getBotReply(uid, message, is_conf, method=''):
    uid = str(uid)
    # special conf messages
    # don't need to reply
    if message is None:
        return None
    message = message.replace('\u0401', '\u0415').replace('\u0451', '\u0435')  # yo
    message = message.replace('\u0490', '\u0413').replace('\u0491', '\u0433')  # g
    message = message.replace('\u0404', '\u042d').replace('\u0454', '\u044d')  # e
    message = message.replace('\u0406', '\u0418').replace('\u0456', '\u0438')  # i
    message = message.replace('\u0407', '\u0418').replace('\u0457', '\u0438')  # i
    answer = bot.interact(('flat' if is_conf == 2 else 'conf ' if is_conf else 'user ') + ('' if is_conf == 2 else uid) + ' ' + message)
    if is_conf == 2:
        bl = answer == '$blacklisted'
        print('Comment', message, '-', 'bad' if bl else 'good')
        return bl
    if answer.startswith('\\'):
        res = preprocessReply(answer[1:], uid)
        log.write('preprocess', '{}: {} ({} -> {})'.format(uid, answer, message, res))
        print(message, ':', answer, '(' + str(res) + ')', end=' ')
        if res is None:
            print('[ERROR] Unknown reply:', res)
            res = ''
        answer = res
    else:
        if message == message.lower() and message != message.upper():
            answer = answer.lower()
        if '{' in answer:
            answer, gender = applyGender(answer, uid)
            print(message, ':', answer, '(female)' if gender == 1 else '(male)', end=' ')
        else:
            print(message, ':', answer, end=' ')
    print('({})'.format(method) if method else '')
    return answer

def processCommand(cmd, *p):
    if cmd == 'reload':
        bot.interact('reld')
        vk.initSelf()
        print('Reloaded!')
        return 'Reloaded!'
    elif cmd == 'banned':
        if banign.banned:
            result = sorted(map(int, banign.banned))
            result = [('conf %d' if j > 2000000000 else 'https://vk.com/id%d') % (j % 2000000000) for j in result]
            return '\n'.join(result)
        else:
            return 'No one banned!'
    elif cmd == 'ignored':
        if banign.ignored:
            result = sorted(map(int, banign.ignored))
            result = [('conf %d' if j > 2000000000 else 'https://vk.com/id%d') % (j % 2000000000) for j in result]
            return '\n'.join(result)
        else:
            return 'No one ignored!'
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
        if not p:
            return 'Not enough parameters'
        user = vk.getUserId(p[-1])
        if user is None:
            return 'No such user'
        if user == admin:
            return 'Cannot ignore admin!'
        return banign.ignore(user)
    elif cmd == 'unignore':
        if not p:
            return 'Not enough parameters'
        user = p[-1]
        if user != '*':
            user = vk.getUserId(user)
        return banign.unignore(user)
    elif cmd == 'leave':
        if not p:
            return 'Not enough parameters'
        cid = p[-1]
        if vk.leaveConf(cid):
            return 'Ok'
        else:
            return 'Fail'
    elif cmd == 'noadd':
        if not p:
            return 'Not enough parameters'
        users = vk.getUserId(p)
        if not users:
            return 'No such users'
        if admin in users:
            return 'Cannot delete admin!'
        check_friend.noadd.update(users)
        vk.deleteFriend(users)
        check_friend.writeNoadd()
        return 'Noadd %s' % str(users)
    else:
        return 'Unknown command'

def reply(m):
    #friendship request
    m['user_id'] = str(m['user_id'])
    if 'chat_id' in m:
        m['chat_id'] = str(m['chat_id'])
        if str(int(m['chat_id']) + 2000000000) in banign.banned:
            return None
    elif m['user_id'] in banign.banned:
        return None
    if 'body' not in m:
        m['body'] = ''
    if m['user_id'] in banign.ignored:
        return ('', 0)
    if vk.users[m['user_id']]['blacklisted'] or vk.users[m['user_id']]['blacklisted_by_me']:
        return ('', 0)
    if 'chat_id' in m:
        m['chat_id'] = str(m['chat_id'])
        if str(int(m['chat_id']) + 2000000000) in banign.ignored:
            return ('', 0)
    if 'id' not in m:
        return (getBotReply(m['user_id'], m['message'], 0), 2)
    m['body'] = preprocessMessage(m)
    if m['body']:
        if m['body'].startswith('\\') and len(m['body']) > 1:
            cmd = m['body'][1:].split()
            if cmd:
                if reset_command and cmd[0] == reset_command:
                    cmd = cmd[1:]
                    vk.sendMessage(admin, '%s from %s' % (cmd, m['user_id']))
                    return (processCommand(*cmd), 1)
                elif m['user_id'] == admin:
                    return (processCommand(*cmd), 1)
        t = evalExpression(m['body'])
        if t:
            print(m['body'], '=', t, '(calculated)')
            log.write('calc', '"{}" = {}'.format(m['body'], t))
            return (t, 0)
        if isBotMessage(m['body']):
            print(m['body'], '- ignored (bot message)')
            return ('', 0)
    if m['body'] and m['body'].upper() == m['body'] and len([i for i in m['body'] if i.isalpha()]) > 1:
        print(m['body'], '- ignored (caps)')
        return ('', 0)
    return (getBotReply(m['user_id'], m['body'] , 'chat_id' in m, m.get('_method', '')), 0)



def preprocessMessage(m, user=None):
    if user is not None and str(m.get('user_id')) != str(user):
        return None
    if 'action' in m:
        if m['action'] == 'chat_create' or (m['action'] == 'chat_invite_user' and str(m['action_mid']) == vk.self_id):
            return 'q'
        if m['action'] == 'chat_title_update':
            return m['action_text'].lower()
        return None
    if 'attachments' in m:
        for a in m['attachments']:
            if a['type'] == 'audio':
                m['body'] += ' [' + a['audio']['title'].lower() + ']'
            elif a['type'] == 'video':
                m['body'] += ' [' + a['video']['title'].lower() + ']'
            elif a['type'] == 'wall':
                m['body'] += ' [' + a['wall']['text'].lower() + ']'
            elif a['type'] == 'doc':
                m['body'] += ' [' + a['doc']['title'].lower() + ']'
            elif a['type'] == 'gift':
                m['body'] += ' vkgift'
            elif a['type'] == 'link':
                m['body'] += ' [' + a['link']['description'].lower() + ']'
    
    if 'fwd_messages' in m:
        for i in m['fwd_messages']:
            if len(m['fwd_messages']) == 1 and str(i.get('user_id')) == vk.self_id and m['body']:
                break
            r = preprocessMessage(i, m.get('user_id'))
            if r is None:
                return None
            m['body'] += ' {' + str(r) + '}'
    if user is None and 'attachments' not in m and not m['body'].strip():
        return None
    if m['body']:
        return m['body'].strip()
    return m['body']


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
        

def applyGender(msg, uid):
    gender = vk.users[uid]['sex'] or 2
    male = re.compile(r'\{m([^\{\}]*)\}')
    female = re.compile(r'\{f([^\{\}]*)\}')
    if gender == 1:
        msg = male.sub('', msg)
        msg = female.sub('\\1', msg)
    else:
        msg = female.sub('', msg)
        msg = male.sub('\\1', msg)
    return msg, gender

def test_friend(uid):
    try:
        fr = vk.api.users.get(user_ids=uid, fields=check_friend.fields)[0]
    except KeyError:
        return 0
    return check_friend.is_good(fr)



if sys.argv[-1] == '-l':
    vkapi.vk_api.logging = 1
    print('Logging enabled')

cfg = list(map(str.strip, open('data.txt').read().strip().splitlines()))
vk = vk_bot(cfg[0], cfg[1], captcha_handler=captcha.solve) # login, pass
print('My id:', vk.self_id)
admin = cfg[2] if len(cfg) > 2 else ''
reset_command = cfg[3] if len(cfg) > 3 else ''


# whether to reply to messages that are already read
reply_all = 0

print('Bot started')

ts = 0

addfriends_interval = config.get('inf.addfriends_interval')
includeread_interval = config.get('inf.includeread_interval')
setonline_interval = config.get('inf.setonline_interval')
unfollow_interval = config.get('inf.unfollow_interval')
filtercomments_interval = config.get('inf.filtercomments_interval')

while 1:
    try:
        vk.replyAll(reply, reply_all)
        reply_all = 0
        if timeto('addfriends', addfriends_interval):
            vk.addFriends(reply, test_friend)
        if timeto('includeread', includeread_interval):
            reply_all = 1
        if timeto('setonline', setonline_interval):
            vk.setOnline()
        if timeto('unfollow', unfollow_interval):
            vk.unfollow(banign.banned)
        if timeto('filtercomments', filtercomments_interval):
            vk.filterComments(lambda s:getBotReply(None, s, 2))
    except Exception as e:
        print('[ERROR] %s: %s' % (e.__class__.__name__, str(e)))
        reply_all = 1
        time.sleep(1)
