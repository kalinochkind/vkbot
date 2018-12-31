import datetime
import html
import json
import logging
import os
import random
import re
import threading
import time

import accounts

import args
import captcha
import config
import log
import stats
import vkapi
import storage
from bot_response import ResponseType, BotResponse
from cache import UserCache, ConfCache, MessageCache
from check_friend import FriendController
from thread_manager import ThreadManager, Timeline
from vkapi import MessageReceiver, CONF_START
from vkapi.utils import getSender

ignored_errors = {
    # (code, method): (message, can_retry)
    (900, 'messages.send'): ('Blacklisted', False),
    (902, 'messages.send'): ('Unable to reply', False),
    (7, 'messages.send'): ('Banned', True),
    (10, 'messages.send'): ('Unable to reply', True),
    (15, 'friends.delete'): None,
    (15, 'messages.setActivity'): None,
    (917, 'messages.setActivity'): None,
    (100, 'messages.markAsRead'): None,
    (100, 'messages.getHistory'): ('Unable to get message history', True),
    (113, 'users.get'): None,
    (100, 'messages.removeChatUser'): ('Unable to leave', False),
    (15, 'messages.removeChatUser'): ('Already kicked', False),
    (8, '*'): (lambda p, m: '{}: error code 8'.format(m), True),
    (10, '*'): (lambda p, m: '{}: error code 10'.format(m), True),
    (100, 'messages.getChat'): None,
}

def createCaptchaHandler():
    captcha_params = {
        'antigate_key': config.get('captcha.antigate_key'),
        'png_filename': accounts.getFile('captcha.png'),
        'txt_filename': accounts.getFile('captcha.txt'),
        'checks_before_antigate': config.get('captcha.checks_before_antigate', 'i'),
        'check_interval': config.get('captcha.check_interval', 'i'),
    }
    return captcha.CaptchaHandler(captcha_params)

def _getFriendControllerParams():
    conf = config.get('friend_checks')
    return {i: conf.get(i) for i in conf}

def createFriendController():
    controller_params = _getFriendControllerParams()
    return FriendController(controller_params, accounts.getFile('allowed.txt'))

def createVkApi(username, password, ignored_errors=None):
    if not ignored_errors:
        ignored_errors = {}
    v = vkapi.VkApi(ignored_errors=ignored_errors, timeout=config.get('vkbot_timing.default_timeout', 'i'),
                token_file=accounts.getFile('token.txt'),
                log_file=accounts.getFile('inf.log') if args.args['logging'] else '', captcha_handler=createCaptchaHandler())
    from vkapi.auth import perms
    v.login_params = {'username': username, 'password': password, 'client_id': config.get('vkapi.client_id'), 'perms': 
                        (perms.FRIENDS | perms.MESSAGES | perms.WALL | perms.OFFLINE | perms.NOTIFICATIONS
                         | perms.PHOTOS | perms.VIDEO | perms.GROUPS)}
    return v


class TimeTracker:
    def __init__(self, size, delay):
        self.times = [0] * size
        self.delay = delay

    def hit(self):
        self.times = self.times[1:] + [time.time()]

    def overload(self):
        return time.time() - self.times[0] < self.delay

class VkBot:
    fields = 'sex,crop_photo,blacklisted,blacklisted_by_me'

    def __init__(self, username='', password='', get_dialogs_interval=60):

        self.delay_on_reply = config.get('vkbot_timing.delay_on_reply', 'i')
        self.chars_per_second = config.get('vkbot_timing.chars_per_second', 'i')
        self.same_user_interval = config.get('vkbot_timing.same_user_interval', 'i')
        self.same_conf_interval = config.get('vkbot_timing.same_conf_interval', 'i')
        self.forget_interval = config.get('vkbot_timing.forget_interval', 'i')
        self.delay_on_first_reply = config.get('vkbot_timing.delay_on_first_reply', 'i')
        self.stats_dialog_count = config.get('stats.dialog_count', 'i')
        self.no_leave_conf = config.get('vkbot.no_leave_conf', 'b')
        self.unfriend_on_invite = config.get('vkbot.unfriend_on_invite', 'b')
        self.unfriend_on_create = config.get('vkbot.unfriend_on_create', 'b')
        self.leave_created_conf = config.get('vkbot.leave_created_conf', 'b')

        self.api = createVkApi(username, password, ignored_errors)
        stats.update('logging', bool(self.api.log_file))
        self.vars = json.load(open('data/defaultvars.json', encoding='utf-8'))
        self.vars['default_bf'] = self.vars['bf']['id']
        self.initSelf(True)
        # hi java
        self.users = UserCache(self.api, self.fields + ',' + FriendController.requiredFields(_getFriendControllerParams()),
                               config.get('cache.user_invalidate_interval', 'i'))
        self.confs = ConfCache(self.api, self.self_id, config.get('cache.conf_invalidate_interval', 'i'))
        self.guid = int(time.time() * 5)
        self.last_viewed_comment = stats.get('last_comment', 0)
        self.good_conf = {}
        self.tm = ThreadManager()
        self.last_message = MessageCache()
        self.tracker = TimeTracker(config.get('vkbot.tracker_message_count', 'i'), config.get('vkbot.tracker_interval', 'i'))
        self.tracker_multiplier = config.get('vkbot.tracker_multiplier', 'f')
        self.receiver = MessageReceiver(self.api, get_dialogs_interval)
        self.receiver.longpoll_callback = self.longpollCallback
        if os.path.isfile(accounts.getFile('msgdump.json')):
            try:
                data = json.load(open(accounts.getFile('msgdump.json')))
                self.last_message.load(data['cache'])
                self.api.longpoll = data['longpoll']
                if len(data['tracker']) == len(self.tracker.times):
                    self.tracker.times = data['tracker']
                self.receiver.last_message_id = data['lmid']
            except Exception:
                logging.exception('Failed to load messages')
            os.remove(accounts.getFile('msgdump.json'))
        else:
            logging.info('Message dump does not exist')
        self.bad_conf_title = lambda s: False
        self.banned_list = []
        self.message_lock = threading.Lock()
        self.ignore_proc = lambda user, reson: None

    @property
    def whitelist(self):
        return self.receiver.whitelist

    @whitelist.setter
    def whitelist(self, new):
        self.receiver.whitelist = new

    def initSelf(self, sync=False):

        def do():
            try:
                res = self.api.users.get(fields='contacts,relation,bdate')[0]
            except IndexError:
                self.api.login()
                do()
                return
            self.self_id = res['id']
            self.vars['phone'] = res.get('mobile_phone') or self.vars['phone']
            self.vars['name'] = (res['first_name'], res['last_name'])
            self.vars['bf'] = res.get('relation_partner') or self.vars['bf']
            try:
                bdate = res['bdate'].split('.')
                today = datetime.date.today()
                self.vars['age'] = today.year - int(bdate[2]) - ((today.month, today.day) < (int(bdate[1]), int(bdate[0])))
            except LookupError:
                pass
            if not sync:
                logging.info('My phone: ' + self.vars['phone'])

        if sync:
            do()
        else:
            threading.Thread(target=do).start()

    def loadUsers(self, arr, key, clean=False):
        users = []
        confs = []
        for i in arr:
            try:
                pid = key(i)
                if pid <= 0:
                    continue
                if pid > CONF_START:
                    confs.append(pid - CONF_START)
                else:
                    users.append(pid)
            except Exception:
                pass
        self.users.load(users, clean)
        self.confs.load(confs, clean)

    def replyOne(self, message, gen_reply):
        if self.whitelist and getSender(message) not in self.whitelist:
            if getSender(message) > CONF_START or getSender(message) < 0:
                return
            if self.users[message['user_id']]['first_name'] + ' ' + self.users[message['user_id']]['last_name'] not in self.whitelist:
                return
        if message['user_id'] == self.self_id:  # chat with myself
            return
        if 'chat_id' in message and not self.checkConf(message['chat_id']):
            self.replyMessage(BotResponse(message, ResponseType.IGNORE))
            return
        try:
            if self.tm.isBusy(getSender(message)) and not self.tm.get(getSender(message)).attr['unimportant']:
                return
        except Exception:
            return
        if message['id'] < self.last_message.bySender(getSender(message)).get('id', 0):
            return

        try:
            ans = gen_reply(message)
        except Exception as e:
            logging.exception('local {}: {}'.format(e.__class__.__name__, str(e)))
            time.sleep(1)
            return
        self.replyMessage(ans)

    def replyAll(self, gen_reply):
        self.tm.gc()
        self.banned_list = []
        messages = self.receiver.getMessages()
        self.loadUsers(messages, lambda x: x['user_id'])
        self.loadUsers(messages, lambda x: x['chat_id'] + CONF_START)
        for cur in messages:
            self.replyOne(cur, gen_reply)
        if self.receiver.used_get_dialogs:
            stats.update('banned_messages', ' '.join(map(str, sorted(self.banned_list))))

    def longpollCallback(self, msg):
        if msg.opt == {'source_mid': str(self.self_id), 'source_act': 'chat_kick_user', 'from': str(self.self_id)}:
            self.good_conf[msg.sender] = False
            del self.confs[msg.sender - CONF_START]
            return True
        if msg.opt.get('source_mid') == str(self.self_id) and msg.opt.get('source_act') == 'chat_invite_user' and msg.sender in self.good_conf:
            del self.good_conf[msg.sender]
            del self.confs[msg.sender - CONF_START]
            return True

        if msg.opt.get('source_act') == 'chat_title_update':
            del self.confs[msg.sender - CONF_START]
            if not storage.contains('banned', msg.sender):
                logging.info('Conf {} ("{}") renamed into "{}"'.format(msg.sender - CONF_START, msg.opt['source_old_text'], msg.opt['source_text']))
            if not self.no_leave_conf and not storage.contains('banned', self.confs[msg.sender - CONF_START]['invited_by']) and self.bad_conf_title(msg.opt['source_text']):
                self.leaveConf(msg.sender - CONF_START)
                log.write('conf', self.loggableConf(msg.sender - CONF_START) + ' (name)')
                return True
        if msg.opt.get('source_act') == 'chat_invite_user' and msg.opt['source_mid'] == str(self.self_id) and msg.opt['from'] != str(self.self_id):
            self.logSender('%sender% added me to conf "{}" ({})'.format(self.confs[msg.sender - CONF_START]['title'], msg.sender - CONF_START),
                           {'user_id': int(msg.opt['from'])})
            if self.unfriend_on_invite and not storage.contains('banned', msg.opt['from']):
                self.deleteFriend(int(msg.opt['from']))
        if msg.opt.get('source_act') == 'chat_create' and msg.opt['from'] != str(self.self_id):
            self.logSender('%sender% created conf "{}" ({})'.format(self.confs[msg.sender - CONF_START]['title'], msg.sender - CONF_START),
                           {'user_id': int(msg.opt['from'])})
            is_banned = storage.contains('banned', msg.opt['from'])
            if self.unfriend_on_create and not is_banned:
                self.deleteFriend(int(msg.opt['from']))
            if not self.no_leave_conf and not is_banned and self.bad_conf_title(self.confs[msg.sender - CONF_START]['title']):
                self.leaveConf(msg.sender - CONF_START)
                log.write('conf', self.loggableName(int(msg.opt['from'])) + ', ' + self.loggableConf(msg.sender - CONF_START) + ' (created, name)')
                return True
        if msg.flags & 2:  # out
            if not msg.opt.get('source_act'):
                self.tm.terminate(msg.sender)
            return True
        try:
            if 'from' in msg.opt and int(msg.opt['from']) != self.tm.get(msg.sender).attr['user_id'] and not msg.opt.get('source_act'):
                self.tm.get(msg.sender).attr['reply'] = True
        except Exception:
            pass

    def sendMessage(self, to, msg, forward=None, sticker_id=None):
        if not self.good_conf.get(to, 1):
            return
        with self.message_lock:
            self.guid += 1
            time.sleep(1)
            self.tracker.hit()
            if sticker_id:
                return self.api.messages.send(peer_id=to, sticker_id=sticker_id, random_id=self.guid)
            elif forward:
                return self.api.messages.send(peer_id=to, message=msg, random_id=self.guid, forward_messages=forward)
            else:
                return self.api.messages.send(peer_id=to, message=msg, random_id=self.guid)

    def replyMessage(self, answer: BotResponse):
        if answer.type == ResponseType.NO_READ:
            return
        sender_msg = self.last_message.bySender(answer.sender_id)
        if answer.message_id <= sender_msg.get('id', 0):
            return

        if answer.type in (ResponseType.NO_RESPONSE, ResponseType.IGNORE):
            if self.tm.isBusy(answer.sender_id):
                return
            if not sender_msg or time.time() - sender_msg['time'] > self.forget_interval:
                tl = Timeline().sleep(self.delay_on_first_reply).do(lambda: self.api.messages.markAsRead(peer_id=answer.sender_id))
                tl.attr['unimportant'] = True
                self.tm.run(answer.sender_id, tl)
            elif answer.type == ResponseType.IGNORE:
                self.api.messages.markAsRead(peer_id=answer.sender_id)
            else:
                tl = Timeline().sleep((self.delay_on_reply - 1) * random.random() + 1).do(lambda: self.api.messages.markAsRead(peer_id=answer.sender_id))
                tl.attr['unimportant'] = True
                self.tm.run(answer.sender_id, tl)
            if answer.type == ResponseType.NO_RESPONSE:
                self.last_message.byUser(answer.user_id)['text'] = answer.message_body
            self.last_message.updateTime(answer.sender_id)
            if answer.sender_id > CONF_START and not answer.message_has_action:
                sender_msg.setdefault('ignored', {})[answer.user_id] = time.time()
            return

        typing_time = 0
        resend = False

        if answer.type == ResponseType.TEXT:
            if not answer.text.startswith('&#'):
                typing_time = len(answer.text) / self.chars_per_second
            if sender_msg.get('reply', '').upper() == answer.text.upper() and sender_msg['user_id'] == answer.user_id:
                logging.info('Resending')
                typing_time = 0
                resend = True

        def _send(attr):
            if not set(sender_msg.get('ignored', [])) <= {answer.user_id}:
                ctime = time.time()
                for uid, ts in sender_msg['ignored'].items():
                    if uid != answer.user_id and ctime - ts < self.same_conf_interval * 3:
                        attr['reply'] = True
            try:
                if answer.type == ResponseType.STICKER:
                    res = self.sendMessage(answer.sender_id, '', sticker_id=answer.data)
                elif resend:
                    res = self.sendMessage(answer.sender_id, '', sender_msg['id'])
                elif attr.get('reply'):
                    res = self.sendMessage(answer.sender_id, answer.text, answer.message_id)
                else:
                    res = self.sendMessage(answer.sender_id, answer.text)
                if res is None:
                    del self.users[answer.sender_id]
                    self.logSender('Failed to send a message to %sender%', answer.fake_message(), short=True)
                    if not answer.is_chat and self.users[answer.user_id].get('blacklisted'):
                        self.ignore_proc(answer.user_id, 'blacklisted me')
                    return
                msg = self.last_message.add(answer.sender_id, answer.message_body, answer.user_id, res, answer.text)
                if resend:
                    msg['resent'] = True
            except Exception as e:
                logging.exception('thread {}: {}'.format(e.__class__.__name__, str(e)))

        cur_delay = (self.delay_on_reply - 1) * random.random() + 1
        send_time = cur_delay + typing_time
        user_delay = 0
        if sender_msg:
            same_interval = self.same_user_interval if answer.sender_id < CONF_START else self.same_conf_interval
            if self.tracker.overload():
                same_interval *= self.tracker_multiplier
            user_delay = sender_msg['time'] - time.time() + same_interval
            # can be negative
        tl = Timeline(max(send_time, user_delay))
        if answer.is_chat:
            tl.attr['user_id'] = answer.user_id
        if not sender_msg or time.time() - sender_msg['time'] > self.forget_interval:
            tl.sleep(self.delay_on_first_reply)
            tl.do(lambda: self.api.messages.markAsRead(peer_id=answer.sender_id))
        else:
            tl.sleepUntil(send_time, (self.delay_on_reply - 1) * random.random() + 1)
            tl.do(lambda: self.api.messages.markAsRead(peer_id=answer.sender_id))

        tl.sleep(cur_delay)
        for action in answer.onsend_actions:
            tl.do(action)
            tl.sleep(cur_delay)
        if typing_time:
            tl.doEveryFor(vkapi.utils.TYPING_INTERVAL,
                          lambda: self.api.messages.setActivity(type='typing', peer_id=answer.sender_id), typing_time)
        tl.do(_send, True)
        self.tm.run(answer.sender_id, tl)

    def checkConf(self, cid):
        if cid + CONF_START in self.good_conf:
            return self.good_conf[cid + CONF_START]
        messages = self.api.messages.getHistory(chat_id=cid)['items']
        for i in messages:
            if i.get('action') == 'chat_invite_user' and i['user_id'] == self.self_id and i.get('action_mid') == self.self_id:
                self.good_conf[cid + CONF_START] = True
                return True
            if self.leave_created_conf and i.get('action') == 'chat_create' and not storage.contains('banned', i['user_id']):
                self.leaveConf(cid)
                log.write('conf',  self.loggableName(i['user_id']) + ', ' + self.loggableConf(cid) + ' (created)')
                return False
            if i.get('action') == 'chat_kick_user' and i['user_id'] == self.self_id and i.get('action_mid') == self.self_id:
                if not storage.contains('banned', self.confs[cid]['invited_by']):
                    inviter = self.confs[cid]['invited_by']
                    self.leaveConf(cid)
                    log.write('conf', (self.loggableName(inviter) if inviter else '(???)') + ', ' + self.loggableConf(cid) + ' (left)')
                    return False
        title = self.confs[cid]['title']
        if not self.no_leave_conf and not storage.contains('banned', self.confs[cid]['invited_by']) and self.bad_conf_title(title):
            self.leaveConf(cid)
            log.write('conf', self.loggableConf(cid) + ' (name)')
            return False
        self.good_conf[cid + CONF_START] = True
        return True

    def leaveConf(self, cid):
        if not self.confs[cid]:
            return False
        logging.info('Leaving conf {} ("{}")'.format(cid, self.confs[cid]['title']))
        self.good_conf[cid + CONF_START] = False
        return self.api.messages.removeChatUser(chat_id=cid, user_id=self.self_id)

    def addFriends(self, is_good):
        data = self.api.friends.getRequests(extended=1)
        if data is None:
            logging.info('Failed to add friends')
            return
        self.loadUsers(data['items'], lambda x: x['user_id'], True)
        with self.api.delayed() as dm:
            for i in data['items']:
                if self.users[i['user_id']].get('blacklisted'):
                    dm.friends.delete(user_id=i['user_id'])
                    continue
                res = is_good(i['user_id'], True)
                if res is None:
                    dm.friends.add(user_id=i['user_id'])
                    self.logSender('Adding %sender%', i)
                else:
                    dm.friends.delete(user_id=i['user_id'])
                    self.logSender('Not adding %sender% ({})'.format(res), i)

    def unfollow(self):
        result = []
        try:
            requests = self.api.friends.getRequests(out=1)['items']
            suggested = self.api.friends.getRequests(suggested=1)['items']
        except TypeError:
            logging.info('Failed to unfollow')
            return []

        for i in requests:
            if not storage.contains('banned', i):
                result.append(i)
        with self.api.delayed() as dm:
            for i in suggested:
                dm.friends.delete.delayed(user_id=i)
        self.deleteFriend(result)
        return result

    def deleteFriend(self, uid):
        if type(uid) == int:
            self.api.friends.delete(user_id=uid)
        else:
            with self.api.delayed() as dm:
                for i in uid:
                    dm.friends.delete(user_id=i)

    def setOnline(self):
        self.api.account.setOnline()

    def getUserId(self, domain, is_conf=False):
        domain = str(domain).lower().rstrip().rstrip('}').rstrip()
        conf = re.search('sel=c(\\d+)', domain) or re.search('^c(\\d+)$', domain) or re.search('chat=(\\d+)', domain) or re.search('peer=2(\\d{9})',
                                                                                                                                   domain)
        if conf is not None:
            return int(conf.group(1)) + CONF_START
        if is_conf:
            if domain.isdigit():
                return int(domain) + CONF_START
            else:
                return None
        if '=' in domain:
            domain = domain.split('=')[-1]
        if '/' in domain:
            domain = domain.split('/')[-1]
        if domain.startswith('-') and domain[1:].isdigit():
            return int(domain)
        data = self.api.users.get(user_ids=domain)
        if not data:
            return None
        return data[0]['id']

    def deleteComment(self, rep):
        if rep['type'] == 'wall':
            self.api.wall.delete(owner_id=self.self_id, post_id=rep['feedback']['id'])
        elif rep['type'].endswith('photo'):
            self.api.photos.deleteComment(owner_id=self.self_id, comment_id=rep['feedback']['id'])
        elif rep['type'].endswith('video'):
            self.api.video.deleteComment(owner_id=self.self_id, comment_id=rep['feedback']['id'])
        else:
            self.api.wall.deleteComment(owner_id=self.self_id, comment_id=rep['feedback']['id'])

    def filterComments(self, test):
        data = self.api.notifications.get(start_time=self.last_viewed_comment + 1, count=100)['items']
        to_del = set()
        to_bl = set()
        self.loadUsers(data, lambda x: x['feedback']['from_id'], True)
        for rep in data:
            if rep['date'] != 'i':
                self.last_viewed_comment = max(self.last_viewed_comment, int(rep['date']))

            def _check(s):
                if 'photo' in s:
                    return s['photo']['owner_id'] == self.self_id
                if 'video' in s:
                    return s['video']['owner_id'] == self.self_id
                if 'post' in s:
                    return s['post']['to_id'] == self.self_id

            if rep['type'] == 'comment_post' and 'parent' in rep and rep['parent'].get('to_id', self.self_id) != self.self_id:
                continue

            if rep['type'].startswith('comment_') or (rep['type'].startswith('reply_comment') and _check(rep['parent'])) or rep['type'] == 'wall':
                txt = html.escape(rep['feedback']['text'])
                res = 'good'
                frid = int(rep['feedback']['from_id'])
                if frid > 0 and self.users[frid]['blacklisted']:
                    res = 'blacklisted'
                    log.write('comments', self.loggableName(frid) + ' (blacklisted): ' + txt)
                    self.deleteComment(rep)
                    to_bl.add(frid)
                elif 'vk.com/' in txt:
                    res = 'link'
                    log.write('comments', self.loggableName(frid) + ' (link): ' + txt)
                    self.deleteComment(rep)
                elif test(txt):
                    res = 'bad'
                    log.write('comments', (self.loggableName(frid) if frid > 0 else str(frid)) + ': ' + txt)
                    self.deleteComment(rep)
                    if frid > 0:
                        to_del.add(frid)
                elif 'attachments' in rep['feedback'] and any(i.get('type') in ['video', 'link'] for i in rep['feedback']['attachments']):
                    res = 'attachment'
                    log.write('comments', self.loggableName(frid) + ' (attachment)')
                    self.deleteComment(rep)
                self.logSender('Comment {} (by %sender%) - {}'.format(txt, res), {'user_id': frid})
        stats.update('last_comment', self.last_viewed_comment)
        for i in to_bl:
            self.blacklist(i)
        return to_del

    def likeAva(self, uid):
        del self.users[uid]
        if 'crop_photo' not in self.users[uid]:
            return
        photo = self.users[uid]['crop_photo']['photo']
        self.api.likes.add(type='photo', owner_id=photo['owner_id'], item_id=photo['id'])
        self.logSender('Liked %sender%', {'user_id': uid})

    def setRelation(self, uid, set_by=None):
        if uid:
            log.write('relation', self.loggableName(uid))
        else:
            log.write('relation', self.loggableName(set_by) + ' (removed)')
            uid = self.vars['default_bf']
        self.api.account.saveProfileInfo(relation_partner_id=uid)
        self.vars['bf'] = self.users[uid]
        self.logSender('Set relationship with %sender%', {'user_id': uid})

    def waitAllThreads(self, loop_thread, reply):
        lp = self.api.longpoll.copy()
        self.receiver.terminate_monitor = True
        loop_thread.join(60)
        while not self.receiver.longpoll_queue.empty():
            self.replyAll(reply)
        self.tm.shutdown(60)
        with open(accounts.getFile('msgdump.json'), 'w') as f:
            json.dump({'cache': self.last_message.dump(), 'longpoll': lp, 'tracker': self.tracker.times, 'lmid': self.receiver.last_message_id}, f)

    # {name} - first_name last_name
    # {id} - id
    def printableName(self, pid, user_fmt, conf_fmt='Conf "{name}" ({id})'):
        if pid > CONF_START:
            return conf_fmt.format(id=(pid - CONF_START), name=self.confs[pid - CONF_START]['title'])
        elif pid > 0:
            return user_fmt.format(id=pid, name=self.users[pid]['first_name'] + ' ' + self.users[pid]['last_name'])
        else:
            return 'Group ' + str(-pid)

    def logSender(self, text, message, short=False):
        text_msg = text.replace('%sender%', self.printableSender(message, False, short=short))
        html_msg = html.escape(text).replace('%sender%', self.printableSender(message, True, short=short))
        logging.info(text_msg, extra={'db': html_msg})

    def printableSender(self, message, need_html, short=False):
        if message.get('chat_id', 0) > 0:
            if short:
                return self.printableName(message['chat_id'] + CONF_START, '', 'conf "{name}" ({id})')
            if need_html:
                res = self.printableName(message['user_id'], user_fmt='Conf "%c" (%i), <a href="https://vk.com/id{id}" target="_blank">{name}</a>')
                return res.replace('%i', str(message['chat_id'])).replace('%c', html.escape(self.confs[message['chat_id']]['title']))
            else:
                res = self.printableName(message['user_id'], user_fmt='Conf "%c" (%i), {name}')
                return res.replace('%i', str(message['chat_id'])).replace('%c', html.escape(self.confs[message['chat_id']]['title']))
        else:
            if need_html:
                return self.printableName(message['user_id'], user_fmt='<a href="https://vk.com/id{id}" target="_blank">{name}</a>')
            else:
                return self.printableName(message['user_id'], user_fmt='{name}')

    def loggableName(self, uid):
        return self.printableName(uid, '{id} ({name})')

    def loggableConf(self, cid):
        return 'conf ({}) `{}`'.format(cid, self.confs[cid]['title'].replace('`', "'"))

    def loggableGroup(self, gid, name):
        return 'group ({}) `{}`'.format(gid, name.replace('`', "'"))

    def blacklist(self, uid):
        self.api.account.banUser(user_id=uid)

    def blacklistedCount(self):
        return self.api.account.getBanned(count=0)['count']

    def lastDialogs(self):

        def cb(req, resp):
            if resp:
                d.append((req['peer_id'], resp['count']))

        dialogs = self.api.messages.getDialogs(count=self.stats_dialog_count, preview_length=1)
        d = []
        confs = {}
        try:
            items = list(dialogs['items'])
            with self.api.delayed() as dm:
                for dialog in items:
                    if storage.contains('banned', getSender(dialog['message'])):
                        continue
                    dm.messages.getHistory(peer_id=getSender(dialog['message']), count=0).set_callback(cb)
                    if 'title' in dialog['message']:
                        confs[getSender(dialog['message'])] = dialog['message']['title']
            self.confs.load([i - CONF_START for i in confs])
            invited = {}
            for i in confs:
                if self.confs[i - CONF_START] and self.confs[i - CONF_START].get('invited_by'):
                    invited[i] = self.confs[i - CONF_START]['invited_by']
            self.users.load(invited.values())
            for i in invited.copy():
                invited[i] = [invited[i], self.printableName(invited[i], '{name}'), self.users[invited[i]]['sex'] == 1]
        except TypeError:
            logging.warning('Unable to fetch dialogs')
            return (None, None, None, None)
        return (dialogs['count'], d, confs, invited)

    def acceptGroupInvites(self):
        for i in self.api.groups.getInvites()['items']:
            logging.info('Joining group "{}"'.format(i['name']))
            self.api.groups.join(group_id=i['id'])
            log.write('groups', '{}: {}{}'.format(
                self.loggableName(i['invited_by']), self.loggableGroup(i['id'], i['name']), ['', ' (closed)', ' (private)'][i['is_closed']]))

    def clearCache(self):
        self.users.clear()
        self.confs.clear()
