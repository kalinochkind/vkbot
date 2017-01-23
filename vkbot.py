import datetime
import html
import json
import logging
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
from cache import UserCache, ConfCache, MessageCache
from check_friend import FriendController
from message_receiver import MessageReceiver
from thread_manager import ThreadManager, Timeline
from vkapi import CONF_START

ignored_errors = {
    # (code, method): (message, can_retry)
    (900, 'messages.send'): ('Blacklisted', False),
    (902, 'messages.send'): ('Unable to reply', False),
    (7, 'messages.send'): ('Banned', True),
    (10, 'messages.send'): ('Unable to reply', True),
    (15, 'friends.delete'): None,
    (100, 'messages.markAsRead'): None,
    (113, 'users.get'): None,
    (100, 'messages.removeChatUser'): ('Unable to leave', False),
    (8, '*'): ('Error code 8', True),
    (10, '*'): ('Error code 10', True),
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
    return {
        'offline_allowed': config.get('check_friend.offline_allowed', 'i'),
        'add_everyone': config.get('vkbot.add_everyone', 'b'),
    }

def createFriendController():
    controller_params = _getFriendControllerParams()
    return FriendController(controller_params, accounts.getFile('noadd.txt'), accounts.getFile('allowed.txt'))

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

        self.api = vkapi.VkApi(username, password, ignored_errors=ignored_errors, timeout=config.get('vkbot_timing.default_timeout', 'i'),
                               token_file=accounts.getFile('token.txt'),
                               log_file=accounts.getFile('inf.log') if args.args['logging'] else '', captcha_handler=createCaptchaHandler())
        self.api.initLongpoll()
        stats.update('logging', bool(self.api.log_file))
        # hi java
        self.users = UserCache(self.api, self.fields + ',' + FriendController.requiredFields(_getFriendControllerParams()),
                               config.get('cache.user_invalidate_interval', 'i'))
        self.confs = ConfCache(self.api, config.get('cache.conf_invalidate_interval', 'i'))
        self.vars = json.load(open('data/defaultvars.json', encoding='utf-8'))
        self.vars['default_bf'] = self.vars['bf']['id']
        self.initSelf(True)
        self.guid = int(time.time() * 5)
        self.last_viewed_comment = stats.get('last_comment', 0)
        self.good_conf = {}
        self.tm = ThreadManager()
        self.last_message = MessageCache()
        self.bad_conf_title = lambda s: False
        self.admin = None
        self.banned_list = []
        self.message_lock = threading.Lock()
        self.banned = set()
        self.receiver = MessageReceiver(self.api, get_dialogs_interval)
        self.receiver.longpoll_callback = self.longpollCallback

    @property
    def whitelist(self):
        return self.receiver.whitelist

    @whitelist.setter
    def whitelist(self, new):
        self.receiver.whitelist = new

    def initSelf(self, sync=False):

        def do():
            res = self.api.users.get(fields='contacts,relation,bdate')[0]
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

    @staticmethod
    def getSender(message):
        if 'chat_id' in message:
            return CONF_START + message['chat_id']
        return message['user_id']

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
        if self.whitelist and self.getSender(message) not in self.whitelist:
            if self.getSender(message) > CONF_START:
                return
            if self.users[message['user_id']]['first_name'] + ' ' + self.users[message['user_id']]['last_name'] not in self.whitelist:
                return
        if 'chat_id' in message and not self.checkConf(message['chat_id']):
            return
        try:
            if self.tm.isBusy(self.getSender(message)) and not self.tm.get(self.getSender(message)).attr['unimportant']:
                return
        except Exception:
            return
        if message['id'] < self.last_message.bySender(self.getSender(message)).get('id', 0):
            return

        try:
            ans = gen_reply(message)
        except Exception as e:
            ans = None
            logging.exception('local {}: {}'.format(e.__class__.__name__, str(e)))
            time.sleep(1)
        if ans:
            self.replyMessage(message, ans[0], ans[1])

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

    # noinspection PyUnusedLocal
    def longpollCallback(self, mid, flags, sender, ts, random_id, text, opt):
        if opt == {'source_mid': str(self.self_id), 'source_act': 'chat_kick_user', 'from': str(self.self_id)}:
            self.good_conf[sender] = False
            return True

        if opt.get('source_act') == 'chat_title_update':
            del self.confs[sender - CONF_START]
            logging.info('Conf {} renamed into "{}"'.format(sender - CONF_START, opt['source_text']))
            if not self.no_leave_conf and self.bad_conf_title(opt['source_text']):
                self.leaveConf(sender - CONF_START)
                log.write('conf', 'conf ' + str(sender - CONF_START) + ' (name: {})'.format(opt['source_text']))
                return True
        if opt.get('source_act') == 'chat_invite_user' and opt['source_mid'] == str(self.self_id) and opt['from'] != str(self.self_id):
            self.logSender('%sender% added me to conf "{}" ({})'.format(self.confs[sender - CONF_START]['title'], sender - CONF_START),
                           {'user_id': int(opt['from'])})
            if not self.no_leave_conf and int(opt['from']) not in self.banned:
                self.deleteFriend(int(opt['from']))
        if flags & 2:  # out
            if not opt.get('source_act'):
                self.tm.terminate(sender)
            return True
        try:
            if 'from' in opt and int(opt['from']) != self.tm.get(sender).attr['user_id'] and not opt.get('source_act'):
                self.tm.get(sender).attr['reply'] = True
        except Exception:
            pass

    def sendMessage(self, to, msg, forward=None):
        if not self.good_conf.get(to, 1):
            return
        with self.message_lock:
            self.guid += 1
            time.sleep(1)
            if forward:
                return self.api.messages.send(peer_id=to, message=msg, random_id=self.guid, forward_messages=forward)
            else:
                return self.api.messages.send(peer_id=to, message=msg, random_id=self.guid)

    def replyMessage(self, message, answer, skip_mark_as_read=False):
        sender = self.getSender(message)
        sender_msg = self.last_message.bySender(sender)
        if 'id' in message and message['id'] <= sender_msg.get('id', 0):
            return

        if not answer:
            if self.tm.isBusy(sender):
                return
            if not sender_msg or time.time() - sender_msg['time'] > self.forget_interval:
                tl = Timeline().sleep(self.delay_on_first_reply).do(lambda: self.api.messages.markAsRead(peer_id=sender))
                tl.attr['unimportant'] = True
                self.tm.run(sender, tl, tl.terminate)
            elif answer is None:  # ignored
                self.api.messages.markAsRead.delayed(peer_id=sender, _once=True)
            else:
                tl = Timeline().sleep((self.delay_on_reply - 1) * random.random() + 1).do(lambda: self.api.messages.markAsRead(peer_id=sender))
                tl.attr['unimportant'] = True
                self.tm.run(sender, tl, tl.terminate)
            self.last_message.byUser(message['user_id'])['text'] = message['body']
            self.last_message.updateTime(sender)
            if sender > CONF_START and 'action' not in message:
                sender_msg.setdefault('ignored', {})[message['user_id']] = time.time()
            return

        typing_time = 0
        if not answer.startswith('&#'):
            typing_time = len(answer) / self.chars_per_second

        resend = False
        # answer is not empty
        if sender_msg.get('reply', '').upper() == answer.upper() and sender_msg['user_id'] == message['user_id']:
            logging.info('Resending')
            typing_time = 0
            resend = True

        def _send(attr):
            if not set(sender_msg.get('ignored', [])) <= {message['user_id']}:
                ctime = time.time()
                for uid, ts in sender_msg['ignored'].items():
                    if uid != message['user_id'] and ctime - ts < self.same_conf_interval * 3:
                        attr['reply'] = True
            try:
                if resend:
                    res = self.sendMessage(sender, '', sender_msg['id'])
                elif attr.get('reply'):
                    res = self.sendMessage(sender, answer, message['id'])
                else:
                    res = self.sendMessage(sender, answer)
                if res is None:
                    del self.users[sender]
                    self.logSender('Failed to send a message to %sender%', message)
                    return
                msg = self.last_message.add(sender, message, res, answer)
                if resend:
                    msg['resent'] = True
            except Exception as e:
                logging.exception('thread {}: {}'.format(e.__class__.__name__, str(e)))

        cur_delay = (self.delay_on_reply - 1) * random.random() + 1
        send_time = cur_delay + typing_time
        user_delay = 0
        if sender_msg and sender != self.admin:
            user_delay = sender_msg['time'] - time.time() + (self.same_user_interval if sender < CONF_START else self.same_conf_interval)
            # can be negative
        tl = Timeline(max(send_time, user_delay))
        if 'chat_id' in message:
            tl.attr['user_id'] = message['user_id']
        if not sender_msg or time.time() - sender_msg['time'] > self.forget_interval:
            if not skip_mark_as_read:
                tl.sleep(self.delay_on_first_reply)
                tl.do(lambda: self.api.messages.markAsRead(peer_id=sender))
        else:
            tl.sleepUntil(send_time, (self.delay_on_reply - 1) * random.random() + 1)
            if not skip_mark_as_read:
                tl.do(lambda: self.api.messages.markAsRead(peer_id=sender))

        tl.sleep(cur_delay)
        if message.get('_onsend_actions'):
            for i in message['_onsend_actions']:
                tl.do(i)
                tl.sleep(cur_delay)
        if typing_time:
            tl.doEveryFor(vkapi.TYPING_INTERVAL, lambda: self.api.messages.setActivity(type='typing', user_id=sender), typing_time)
        tl.do(_send, True)
        self.tm.run(sender, tl, tl.terminate)

    def checkConf(self, cid):
        if self.no_leave_conf:
            return True
        if cid + CONF_START in self.good_conf:
            return self.good_conf[cid + CONF_START]
        messages = self.api.messages.getHistory(chat_id=cid)['items']
        for i in messages:
            if i.get('action') == 'chat_create' and i['user_id'] not in self.banned:
                self.leaveConf(cid)
                self.deleteFriend(i['user_id'])
                log.write('conf', self.loggableName(i.get('user_id')) + ' ' + str(cid))
                return False
        title = self.confs[cid]['title']
        if self.bad_conf_title(title):
            self.leaveConf(cid)
            log.write('conf', 'conf ' + str(cid) + ' (name: {})'.format(title))
            return False
        self.good_conf[cid + CONF_START] = True
        return True

    def leaveConf(self, cid):
        if not self.confs[cid]:
            return False
        logging.info('Leaving conf {} ("{}")'.format(cid, self.confs[cid]['title']))
        self.good_conf[cid + CONF_START] = False
        return self.api.messages.removeChatUser(chat_id=cid, user_id=self.self_id)

    def addFriends(self, gen_reply, is_good):
        data = self.api.friends.getRequests(extended=1)
        to_rep = []
        self.loadUsers(data['items'], lambda x: x['user_id'], True)
        for i in data['items']:
            if self.users[i['user_id']].get('blacklisted'):
                self.api.friends.delete.delayed(user_id=i['user_id'])
                continue
            res = is_good(i['user_id'], True)
            if res is None:
                self.api.friends.add.delayed(user_id=i['user_id'])
                self.logSender('Adding %sender%', i)
                if 'message' in i:
                    ans = gen_reply(i)
                    to_rep.append((i, ans))
            else:
                self.api.friends.delete.delayed(user_id=i['user_id'])
                self.logSender('Not adding %sender% ({})'.format(res), i)
        for i in to_rep:
            self.replyMessage(i[0], i[1][0], i[1][1])
        self.api.sync()

    def unfollow(self):
        result = []
        requests = self.api.friends.getRequests(out=1)['items']
        suggested = self.api.friends.getRequests(suggested=1)['items']
        for i in requests:
            if i not in self.banned:
                result.append(i)
        for i in suggested:
            self.api.friends.delete.delayed(user_id=i)
        self.deleteFriend(result)
        return result

    def deleteFriend(self, uid):
        if type(uid) == int:
            self.api.friends.delete(user_id=uid)
        else:
            for i in uid:
                self.api.friends.delete.delayed(user_id=i)
            self.api.sync()

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

            if rep['type'].startswith('comment_') or (rep['type'].startswith('reply_comment') and _check(rep['parent'])) or rep['type'] == 'wall':
                txt = html.escape(rep['feedback']['text'])
                res = 'good'
                frid = int(rep['feedback']['from_id'])
                if self.users[frid]['blacklisted']:
                    res = 'blacklisted'
                    log.write('comments', self.loggableName(frid) + ' (blacklisted): ' + txt)
                    self.deleteComment(rep)
                    to_bl.add(frid)
                elif test(txt):
                    res = 'bad'
                    log.write('comments', self.loggableName(frid) + ': ' + txt)
                    self.deleteComment(rep)
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

    def setRelation(self, uid):
        if uid:
            log.write('relation', self.loggableName(uid))
        else:
            log.write('relation', 'Removed')
            uid = self.vars['default_bf']
        self.api.account.saveProfileInfo(relation_partner_id=uid)
        self.vars['bf'] = self.users[uid]
        self.logSender('Set relationship with %sender%', {'user_id': uid})

    def waitAllThreads(self):
        for t in self.tm.all():
            t.join(60)

    # {name} - first_name last_name
    # {id} - id
    def printableName(self, pid, user_fmt, conf_fmt='Conf "{name}" ({id})'):
        if pid > CONF_START:
            return conf_fmt.format(id=(pid - CONF_START), name=self.confs[pid - CONF_START]['title'])
        else:
            return user_fmt.format(id=pid, name=self.users[pid]['first_name'] + ' ' + self.users[pid]['last_name'])

    def logSender(self, text, message):
        text_msg = text.replace('%sender%', self.printableSender(message, False))
        html_msg = text.replace('%sender%', self.printableSender(message, True))
        logging.info(text_msg, extra={'db': html_msg})

    def printableSender(self, message, need_html):
        if message.get('chat_id', 0) > 0:
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

    def blacklist(self, uid):
        self.api.account.banUser(user_id=uid)

    def blacklistedCount(self):
        return self.api.account.getBanned(count=0)['count']

    def lastDialogs(self):

        def cb(req, resp):
            d.append((req['peer_id'], resp['count']))

        dialogs = self.api.messages.getDialogs(count=self.stats_dialog_count, preview_length=1)
        d = []
        confs = {}
        try:
            items = list(dialogs['items'])
            for dialog in items:
                if self.getSender(dialog['message']) in self.banned:
                    continue
                self.api.messages.getHistory.delayed(peer_id=self.getSender(dialog['message']), count=0).callback(cb)
                if 'title' in dialog['message']:
                    confs[self.getSender(dialog['message'])] = dialog['message']['title']
            self.api.sync()
        except TypeError:
            logging.warning('Unable to fetch dialogs')
            return (None, None, None)
        return (dialogs['count'], d, confs)

    def acceptGroupInvites(self):
        for i in self.api.groups.getInvites()['items']:
            logging.info('Joining group "{}"'.format(i['name']))
            self.api.groups.join(group_id=i['id'])
            log.write('groups', '{}: <a target="_blank" href="https://vk.com/club{}">{}</a>{}'.format(
                self.loggableName(i['invited_by']), i['id'], i['name'], ['', ' (closed)', ' (private)'][i['is_closed']]))

    def clearCache(self):
        self.users.clear()
        self.confs.clear()
