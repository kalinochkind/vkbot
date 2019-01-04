#!/usr/bin/python3

import html
import logging
import random
import re
import signal
import sys
import threading
import time
import json

import accounts
import config
import log
import stats
import vkbot
import storage
from bot_response import BotResponse, ResponseType
from cache import LimiterCache
from calc import evalExpression
from cppbot import CppBot
from prepare import login, password
from server import MessageServer
from vkapi import CONF_START
from vkbot_message import VkbotMessage, PeerInfo


def isBotMessage(msg, regex=re.compile(r'^\(.+\).')):
    return regex.match(msg.strip())

noans = open(accounts.getFile('noans.txt'), encoding='utf-8').read().splitlines()
smiles = open(accounts.getFile('smiles.txt'), encoding='utf-8').read().splitlines()
random.shuffle(noans)

# noinspection PyDefaultArgument
def timeto(name, interval, d={}):
    if interval >= 0 and time.time() > d.get(name, 0) + interval:
        d[name] = time.time()
        return True
    return False

def renderSmile(s, regex=re.compile(r'&#(\d+);')):
    return regex.sub(lambda x: chr(int(x.group(1))), s)


last_reply_lower = set()
_sticker_re = re.compile(r'^\\sticker\[(\d+)\]$')
_cmd_re = re.compile(r'\\([a-zA-Z]+)((?:\[[^\]]+\])*)')

def getBotReplyComment(message):
    return bot.interact('comm ' + CppBot.escape(message)) == '$blacklisted'

def getBotReplyFlat(message):
    return bot.interact('flat 0 ' + CppBot.escape(message)) == '$blacklisted'


def getBotReply(message: VkbotMessage):
    raw_answer = bot.interact('{} {} {} | {}'.format(('conf' if message.is_chat else 'user'), message.user_id,
                                                     limiter_cache.get(message.peer_id),
                                                     CppBot.escape(message.processed_body)))
    if '|' in raw_answer:
        limiters, answer = raw_answer.split('|', maxsplit=1)
    else:
        limiters = ''
        answer = raw_answer
    limiter_cache.add(message.peer_id, limiters)

    if answer == '$noans' and not (message.is_sticker and message.is_chat):
        if (message.processed_body.upper() == message.processed_body.lower()
                and '?' not in message.processed_body) or message.is_sticker:
            answer = random.choice(smiles)
        else:
            answer = noans[0]
            next_ans = random.randint(1, len(noans) - 1)
            noans[0], noans[next_ans] = noans[next_ans], noans[0]
    elif answer == '$blacklisted' or answer == '$noans':
        answer = ''

    console_message = ''

    if '{' in answer:
        answer, gender = applyGender(answer, message.user_id)
        console_message += ' (' + gender + ')'

    sticker_id = None
    onsend_actions = []
    while '\\' in answer:
        sticker = _sticker_re.match(answer)
        if sticker:
            console_message += ' (' + answer + ')'
            answer = ''
            sticker_id = int(sticker.group(1))
            break
        res = _cmd_re.sub(lambda m: preprocessReply(m.group(1), m.group(2).strip('][').split(']['),
                          message.user_id, onsend_actions), answer)
        console_message += ' (' + answer + ')'
        answer = res

    case = message.get_answer_case()
    if case == 'lower':
        last_reply_lower.add(message.user_id)
    elif case == 'normal':
        last_reply_lower.discard(message.user_id)
    if message.user_id in last_reply_lower:
        answer = answer.lower()

    if message.method != 'longpoll':
        console_message += ' (' + message.method + ')'
    text_msg = '({}) {} : {}{}'.format(vk.printableSender(message.get_peer_info(), False),
                                       message.processed_body, renderSmile(answer), console_message)
    html_msg = '({}) {} : {}{}'.format(vk.printableSender(message.get_peer_info(), True),
                                       html.escape(message.processed_body), renderSmile(answer).replace('&', '&amp;'),
                                       console_message)
    logging.info(text_msg, extra={'db': html_msg})

    if sticker_id is not None:
        return BotResponse(message, ResponseType.STICKER, sticker_id, onsend_actions=onsend_actions)
    elif answer:
        return BotResponse(message, ResponseType.TEXT, answer, onsend_actions=onsend_actions)
    else:
        return BotResponse(message, ResponseType.NO_RESPONSE, onsend_actions=onsend_actions)


bot_users = {}

limiter_cache = LimiterCache('data/limiters.txt')

ref_re = re.compile(r'\[id(\d+)\|.*\]')
club_ref_re = re.compile(r'\[club\d+\|.*\]')


def reply(message: VkbotMessage):
    if message.peer_id < 0 or storage.contains('banned', message.peer_id):
        return BotResponse(message, ResponseType.NO_READ)
    uid = message.user_id
    if uid < 0 and storage.contains('banned', uid):
        return BotResponse(message, ResponseType.IGNORE)
    if message.is_chat and not vk.no_leave_conf and (uid < 0 or storage.contains('bots', uid)):
        logging.info('A bot detected' + (' (group)' if uid < 0 else ''))
        log.write('conf', vk.loggableConf(message.chat_id) + ' (bot found)')
        vk.leaveConf(message.chat_id)
        return BotResponse(message, ResponseType.IGNORE)
    if storage.contains('ignored', message.peer_id) or storage.contains('ignored', uid):
        return BotResponse(message, ResponseType.IGNORE)
    if uid < 0:
        return BotResponse(message, ResponseType.IGNORE)
    if 'deactivated' in vk.users[uid] or vk.users[uid]['blacklisted'] or vk.users[uid]['blacklisted_by_me']:
        return BotResponse(message, ResponseType.IGNORE)
    if message.body is None:
        # chat actions
        return BotResponse(message, ResponseType.IGNORE)

    if isBotMessage(message.body):
        vk.logSender('(%sender%) {} - ignored (bot message)'.format(CppBot.escape(message.body)),
                     message.get_peer_info())
        if message.is_chat and not vk.no_leave_conf:
            bot_users[uid] = bot_users.get(uid, 0) + 1
            if bot_users[uid] >= 3:
                logging.info('Too many bot messages')
                log.write('conf', vk.loggableConf(message.chat_id) + ' (bot messages)')
                vk.leaveConf(message.chat_id)
                return BotResponse(message, ResponseType.NO_RESPONSE)
    elif uid in bot_users:
        del bot_users[uid]

    if message.processed_body is None:
        return BotResponse(message, ResponseType.NO_RESPONSE)
    if not message.processed_body:
        return getBotReply(message)


    if message.is_sticker and message.is_chat:
        return BotResponse(message, ResponseType.NO_RESPONSE)
    if message.is_sticker and config.get('vkbot.ignore_stickers', 'b'):
        vk.logSender('(%sender%) {} - ignored'.format(message.processed_body), message.get_peer_info())
        return BotResponse(message, ResponseType.NO_RESPONSE)
    if message.is_voice and message.is_chat:
        vk.logSender('(%sender%) {} - ignored'.format(message.processed_body), message.get_peer_info())
        return BotResponse(message, ResponseType.NO_RESPONSE)
    if len(message.processed_body) > config.get('vkbot.max_message_length', 'i'):
        vk.logSender('(%sender%) {}... - too long message'.format(message.processed_body[:50]), message.get_peer_info())
        return BotResponse(message, ResponseType.NO_RESPONSE)
    if not (set(ref_re.findall(message.body)) <= {str(vk.self_id)}):
        vk.logSender('(%sender%) {} - ignored (mention)'.format(message.processed_body), message.get_peer_info())
        return BotResponse(message, ResponseType.NO_RESPONSE)
    if club_ref_re.findall(message.body):
        return BotResponse(message, ResponseType.NO_RESPONSE)
    user_msg = vk.last_message.byUser(uid)
    if message.processed_body == user_msg.get('text') and message.processed_body != '..':
        user_msg['count'] = user_msg.get('count', 0) + 1  # this modifies the cache entry too
        if message.is_voice and user_msg == vk.last_message.bySender(message.peer_id) and not user_msg.get('resent'):
            vk.logSender('(%sender%) - voice again', message.get_peer_info())
            return BotResponse(message, ResponseType.TEXT, user_msg.get('reply'))
        if message.is_sticker:
            return BotResponse(message, ResponseType.NO_RESPONSE)
        if user_msg['count'] == 5:
            noaddUsers([uid], reason='flood')
        elif user_msg['count'] < 5:
            vk.logSender('(%sender%) {} - ignored (repeated)'.format(message.body), message.get_peer_info())
        return BotResponse(message, ResponseType.NO_RESPONSE)

    if 'reply' in user_msg and message.body.upper() == user_msg['reply'].upper() and len(message.body.split()) > 1:
        vk.logSender('(%sender%) {} - ignored (my reply)'.format(message.processed_body), message.get_peer_info())
        user_msg['text'] = user_msg['reply']  # this modifies the cache entry too
        return BotResponse(message, ResponseType.NO_RESPONSE)

    t = evalExpression(message.body)
    if t:
        if getBotReplyFlat(message.processed_body):
            return BotResponse(message, ResponseType.NO_RESPONSE)
        vk.logSender('(%sender%) {} = {} (calculated)'.format(message.processed_body, t), message.get_peer_info())
        log.write('calc', '{}: "{}" = {}'.format(vk.loggableName(uid), message.body, t))
        return BotResponse(message, ResponseType.NO_RESPONSE)
    tbody = message.body.replace('<br>', '')
    if tbody.upper() == tbody and sum(i.isalpha() for i in tbody) > 1 and config.get('vkbot.ignore_caps', 'b'):
        vk.logSender('(%sender%) {} - ignored (caps)'.format(message.processed_body), message.get_peer_info())
        return BotResponse(message, ResponseType.NO_RESPONSE)

    return getBotReply(message)


def preprocessReply(s, params, uid, onsend_actions):
    if s == 'myname':
        return vk.users[uid]['first_name']
    if s == 'mylastname':
        return vk.users[uid]['last_name']
    if s == 'curtime':
        return time.strftime("%k:%M", time.localtime()).lstrip()
    if s == 'gosp':
        onsend_actions.append(lambda: vk.setRelation(uid))
        return ''
    if s == 'rmsp':
        onsend_actions.append(lambda: vk.setRelation(None, uid))
        return ''
    if s == 'phone':
        return vk.vars['phone']
    if s == 'age':
        return str(vk.vars['age'])
    if s == 'name':
        return vk.vars['name'][0]
    if s == 'lastname':
        return vk.vars['name'][1]
    if s == 'bf':
        if vk.vars['bf']:
            return 'https://vk.com/id' + str(vk.vars['bf']['id'])
        else:
            return ''
    if s == 'bfname':
        if vk.vars['bf']:
            return vk.vars['bf']['first_name']
        else:
            return ''
    if s == 'bflastname':
        if vk.vars['bf']:
            return vk.vars['bf']['last_name']
        else:
            return ''
    if s == 'ifbf':
        if len(params) != 2:
            logging.error('ifbf: 2 arguments required')
            return ''
        if uid == vk.vars['bf']['id']:
            return params[0]
        else:
            return params[1]
    logging.error('Unknown variable: ' + s)

# 1: female, 2: male
def applyGender(msg, uid, male_re=re.compile(r'\{m([^{}]*)\}'), female_re=re.compile(r'\{f([^{}]*)\}')):
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
    return friend_controller.isGood(fr, need_reason)

def noaddUsers(users, remove=False, reason=None, sure=False):
    users = set(users)
    if not users:
        return 0
    vk.users.load(users)
    if not remove and config.get('vkbot.no_ignore', 'b') and not sure:
        for i in users:
            vk.logSender('Wanted to ignore %sender% ({})'.format(reason), PeerInfo(i))
        return 0
    if remove:
        return storage.deletemany('ignored', users)
    else:
        deleted = []
        for user in users:
            if storage.add('ignored', user):
                deleted.append(user)
        if not deleted:
            return 0
        text_msg = 'Deleting ' + ', '.join([vk.printableSender(PeerInfo(i), False) for i in deleted]) + (
            ' ({})'.format(reason) if reason else '')
        html_msg = 'Deleting ' + ', '.join([vk.printableSender(PeerInfo(i), True) for i in deleted]) + (
            ' ({})'.format(reason) if reason else '')
        logging.info(text_msg, extra={'db': html_msg})
        vk.deleteFriend(deleted)
        return len(deleted)

# noinspection PyUnusedLocal
def reloadHandler(*p):
    global friend_controller
    friend_controller = vkbot.createFriendController()
    bot.reload()
    vk.initSelf()
    vk.clearCache()
    return 'Reloaded!'

# noinspection PyUnusedLocal
def onExit(num, frame):
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    logging.info('Received ' + ('SIGTERM' if num == signal.SIGTERM else 'SIGINT'))
    vk.waitAllThreads(loop_thread, reply if includeread_interval >= 0 else lambda x: None)
    logging.info('Bye')
    bot.dump()
    logging.shutdown()
    sys.exit()


signal.signal(signal.SIGTERM, onExit)
signal.signal(signal.SIGINT, onExit)

includeread_interval = config.get('intervals.includeread', 'i')
vk = vkbot.VkBot(login, password, includeread_interval)
bot = CppBot(vk.vars['name'][0], config.get('vkbot.max_smiles', 'i'), accounts.getFile('chatdump.dat'))
vk.bad_conf_title = lambda s: getBotReplyFlat(' ' + s)

logging.info('I am {}, {}'.format(vk.vars['name'][0], vk.self_id))

addfriends_interval = config.get('intervals.addfriends', 'i')
setonline_interval = config.get('intervals.setonline', 'i')
unfollow_interval = config.get('intervals.unfollow', 'i')
filtercomments_interval = config.get('intervals.filtercomments', 'i')
stats_interval = config.get('intervals.stats', 'i')

def listHandler(data):
    data = json.loads(data)
    user = vk.getUserId(data['uid'])
    if not user:
        return '{"error": "Invalid user"}'
    if data.get('remove'):
        result = storage.delete(data['list'], user)
    else:
        result = storage.add(data['list'], user)
        if data['list'] == 'ignored' and result:
            vk.deleteFriend(user)
    return json.dumps({'name': vk.printableName(user, user_fmt='{name}'), 'success': result})

def isignoredHandler(user):
    user = vk.getUserId(user)
    if user is None or user > CONF_START:
        return 'Invalid user'
    r = testFriend(user, True)
    if r is None:
        return 'Good'
    return r

def leaveHandler(conf):
    conf = vk.getUserId(conf, True)
    if conf is None:
        return 'Fail'
    if conf > CONF_START:
        conf -= CONF_START
    if vk.leaveConf(conf):
        return 'Ok'
    else:
        return 'Fail'

def runScriptHandler(msg):

    from scripts import runScript

    def _run():
        try:
            runScript(data['name'], data['args'], api)
        except BaseException:
            logging.exception('Uncaught exception in script')
        logging.info('Script %s exited successfully', data['name'])

    data = json.loads(msg)
    api = vkbot.createVkApi(login, password)
    api.limiter = vk.api.limiter
    t = threading.Thread(target=_run)
    t.start()
    logging.info('Running script %s', data['name'])
    return 'ok'


if config.get('server.port', 'i') > 0:
    srv = MessageServer(config.get('server.port', 'i'))
    srv.addHandler('reply', lambda x: bot.interact('flat ' + CppBot.escape(x), False))
    srv.addHandler('stem', lambda x: bot.interact('stem ' + CppBot.escape(x), False))
    srv.addHandler('list', listHandler)
    srv.addHandler('reload', reloadHandler)
    srv.addHandler('isignored', isignoredHandler)
    srv.addHandler('leave', leaveHandler)
    srv.addHandler('runscript', runScriptHandler)
    srv.listen()
    logging.info('Running TCP server on port ' + config.get('server.port'))

friend_controller = vkbot.createFriendController()
stats.update('started', time.time())
vk.ignore_proc = lambda user, reason: noaddUsers([user], reason=reason, sure=True)

def main_loop():
    try:
        if timeto('setonline', setonline_interval):
            vk.setOnline()
        if timeto('filtercomments', filtercomments_interval):
            noaddUsers(vk.filterComments(lambda s: getBotReplyComment(s)), reason='bad comment')
        if timeto('unfollow', unfollow_interval):
            noaddUsers(vk.unfollow(), reason='deleted me')
        if timeto('addfriends', addfriends_interval):
            vk.addFriends(testFriend)
        if includeread_interval >= 0:
            vk.replyAll(reply)
        else:
            vk.replyAll(lambda x: None)
            time.sleep(1)
        if timeto('stats', stats_interval):
            vk.initSelf(True)
            stats.update('ignored', storage.count('ignored'))
            stats.update('blacklisted', vk.blacklistedCount())
            count, dialogs, confs, invited = vk.lastDialogs()
            if count is not None:
                vk.loadUsers(dialogs, lambda x: x[0])
                dialogs = [[uid, vk.printableName(uid, '{name}', conf_fmt='Conf "%s"' % confs.get(uid).replace('{', '{{').replace('}', '}}')), cnt, invited.get(uid)]
                           for uid, cnt in dialogs if uid > 0]
                stats.update('dialogs', count)
                stats.update('dialogs_list', dialogs)
                stats.update('phone', vk.vars['phone'])
                stats.update('bf', vk.printableSender(PeerInfo(vk.vars['bf']['id']), True))
                stats.update('overload', vk.tracker.overload())
        bot.reloadIfChanged()
    except Exception as e:
        logging.exception('global {}: {}'.format(e.__class__.__name__, str(e)))
        time.sleep(2)

while True:
    loop_thread = threading.Thread(target=main_loop)
    loop_thread.start()
    time.sleep(1)
    loop_thread.join()
