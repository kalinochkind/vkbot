#!/usr/bin/python3

import time
import sys
from subprocess import Popen, PIPE
from vkbot import vk_bot
import captcha
import re
import check_friend
from calc import evalExpression
import log
import config

bot_msg = re.compile(r'^\(.+\)')
friend_cache = {}

def writeBannedIgnored():
    s = ['$' + i for i in sorted(banned, key=int)] + sorted(ignored, key=int)
    with open('banned.txt', 'w') as f:
        f.write('\n'.join(s))        

def sendToBot(msg):
    bot.stdin.write(msg.replace('\n', '\a').strip().encode() + b'\n')
    bot.stdin.flush()
    answer = bot.stdout.readline().rstrip().replace(b'\a', b'\n')
    return answer.decode().strip()

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
    answer = sendToBot(('flat' if is_conf == 2 else 'conf ' if is_conf else 'user ') + ('' if is_conf == 2 else uid) + ' ' + message)
    if is_conf == 2:
        bl = answer == '\\blacklisted'
        print('Comment', message, '-', 'bad' if bl else 'good')
        return bl
    if answer.startswith('\\'):
        res = preprocessReply(answer[1:], uid)
        print(message, ':', answer, '(' + str(res) + ')', end=' ')
        if res is None:
            print('[ERROR] Unknown reply:', res)
            res = ''
        answer = res
    elif '{' in answer:
        answer, gender = applyGender(answer, uid)
        print(message, ':', answer, '(female)' if gender == 1 else '(male)', end=' ')
    else:
        print(message, ':', answer, end=' ')
    print('({})'.format(method) if method else '')
    return answer

def isFriend(uid):
    if uid not in friend_cache:
        friend_cache[uid] = vk.isFriend(uid)
    return friend_cache[uid]

def processCommand(cmd, *p):
    global banned
    global ignored
    if cmd == 'reload':
        sendToBot('reld')
        print('Reloaded!')
        return 'Reloaded!'
    elif cmd == 'banned':
        if banned:
            result = sorted(map(int, banned))
            result = [('conf %d' if j < 5000 else 'https://vk.com/id%d') % j for j in result]
            return '\n'.join(result)
        else:
            return 'No one banned!'
    elif cmd == 'ignored':
        if ignored:
            result = sorted(map(int, ignored))
            result = [('conf %d' if j < 5000 else 'https://vk.com/id%d') % j for j in result]
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
        banned.add(user)
        writeBannedIgnored()
        print('User %s banned' % user)
        return 'User %s banned' % user
    elif cmd == 'unban':
        if not p:
            return 'Not enough parameters'
        user = p[-1]
        if user == '*':
            banned = set()
        else:
            user = vk.getUserId(user)
            banned.discard(user)
        writeBannedIgnored()
        print('User %s unbanned' % user)
        return 'User %s unbanned' % user
    elif cmd == 'ignore':
        if not p:
            return 'Not enough parameters'
        user = vk.getUserId(p[-1])
        if user is None:
            return 'No such user'
        if user == admin:
            return 'Cannot ignore admin!'
        ignored.add(user)
        writeBannedIgnored()
        print('User %s ignored' % user)
        return 'User %s ignored' % user
    elif cmd == 'unignore':
        if not p:
            return 'Not enough parameters'
        user = p[-1]
        if user == '*':
            ignored = set()
        else:
            user = vk.getUserId(user)
            ignored.discard(user)
        writeBannedIgnored()
        print('User %s unignored' % user)
        return 'User %s unignored' % user
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
        user = vk.getUserId(p[-1])
        if user is None:
            return 'No such user'
        if user == admin:
            return 'Cannot delete admin!'
        check_friend.noadd.add(str(user))
        check_friend.writeNoadd()
        vk.deleteFriend(user)
        return 'Noadd %s' % user
    else:
        return 'Unknown command'

def reply(m):
    #friendship request
    m['user_id'] = str(m['user_id'])
    if 'chat_id' in m:
        m['chat_id'] = str(m['chat_id'])
        if m['chat_id'] in banned:
            return None
    elif m['user_id'] in banned:
        return None
  #  elif not isFriend(m['user_id']):
  #      return ('', 0)
    if 'body' not in m:
        m['body'] = ''
    if m['user_id'] in ignored:
        return ('', 0)
    if 'chat_id' in m:
        m['chat_id'] = str(m['chat_id'])
        if m['chat_id'] in ignored:
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
        if bot_msg.match(m['body'].strip()):
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
        return vk.getUserInfo(uid)['first_name']
    if s == 'mylastname':
        return vk.getUserInfo(uid)['last_name']
    if s == 'curtime':
        return time.strftime("%H:%M", time.localtime())
    if s.startswith('likeava'):
        vk.likeAva(uid)
        return s.split(maxsplit=1)[1]
    if s.startswith('gosp'):
        vk.setRelation(uid)
        return s.split(maxsplit=1)[1]
        

def applyGender(msg, uid):
    gender = vk.getUserInfo(uid)['sex'] or 2
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


_timeto = {}
def timeto(name, interval):
    if time.time() > _timeto.get(name, 0) + interval:
        _timeto[name] = time.time()
        return 1
    return 0

bot = Popen(['./chat.exe'], stdout=PIPE, stdin=PIPE)
cfg = list(map(str.strip, open('data.txt').read().strip().splitlines()))
vk = vk_bot(cfg[0], cfg[1], captcha_handler=captcha.solve) # login, pass
print('My id:', vk.self_id)
admin = cfg[2] if len(cfg) > 2 else ''
reset_command = cfg[3] if len(cfg) > 3 else ''

banign = open('banned.txt').read().split()
banned = set(i[1:] for i in banign if i.startswith('$'))
ignored = set(i for i in banign if not i.startswith('$'))

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
            vk.unfollow(banned)
        if timeto('filtercomments', filtercomments_interval):
            vk.filterComments(lambda s:getBotReply(None, s, 2))
    except Exception as e:
        print('[ERROR] %s: %s' % (e.__class__.__name__, str(e)))
        reply_all = 1
        time.sleep(1)
