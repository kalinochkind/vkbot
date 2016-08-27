import vkapi
import time
import log
from thread_manager import ThreadManager, Timeline
from cache import UserCache, ConfCache, MessageCache
import config
import re
import random
import html
import stats
import check_friend
import threading

CONF_START = 2000000000

ignored_errors = {
    # (code, method): (message, can_retry)
    (900, 'messages.send'): ('Blacklisted', False),
    (7, 'messages.send'): ('Banned', True),
    (10, 'messages.send'): ('Unable to reply', True),
    (15, 'friends.delete'): None,
    (100, 'messages.markAsRead'): None,
    (113, 'users.get'): None,
    (100, 'messages.removeChatUser'): ('Unable to leave', False),
    (8, '*'): ('Error code 8', True),
    (10, '*'): ('Error code 10', True),
}

class VkBot:

    delay_on_reply = config.get('vkbot.delay_on_reply', 'i')
    chars_per_second = config.get('vkbot.chars_per_second', 'i')
    same_user_interval = config.get('vkbot.same_user_interval', 'i')
    same_conf_interval = config.get('vkbot.same_conf_interval', 'i')
    typing_interval = 5
    forget_interval = config.get('vkbot.forget_interval', 'i')
    delay_on_first_reply = config.get('vkbot.delay_on_first_reply', 'i')
    stats_dialog_count = config.get('vkbot.stats_dialog_count', 'i')

    def __init__(self, username='', password=''):
        self.api = vkapi.VkApi(username, password, ignored_errors=ignored_errors)
        self.api.initLongpoll()
        self.users = UserCache(self.api, 'sex,crop_photo,blacklisted,blacklisted_by_me,' + check_friend.fields)
        self.confs = ConfCache(self.api)
        self.initSelf()
        self.guid = int(time.time() * 5)
        self.last_viewed_comment = stats.get('last_comment', 0)
        self.good_conf = {}
        self.tm = ThreadManager()
        self.last_message = MessageCache()
        self.last_message_id = 0
        self.whitelist = None
        self.bad_conf_title = lambda s: False
        self.admin = None
        self.banned_list = []
        self.message_lock = threading.Lock()

    def initSelf(self):
        self.users.clear()
        res = self.api.users.get(fields='contacts,relation')[0]
        self.self_id = res['id']
        self.phone = res.get('mobile_phone', '')
        self.name = (res['first_name'], res['last_name'])
        self.bf = res.get('relation_partner')
        log.info('My phone: ' + self.phone)

    @staticmethod
    def getSender(message):
        if 'chat_id' in message:
            return CONF_START + message['chat_id']
        return message['user_id']

    def loadUsers(self, arr, key, clean=False, confs=False):
        users = []
        for i in arr:
            try:
                users.append(key(i))
            except Exception:
                pass
        (self.confs if confs else self.users).load(users, clean)

    def replyOne(self, message, gen_reply, method=None):
        if self.whitelist and self.getSender(message) not in self.whitelist:
            return
        if 'chat_id' in message and not self.checkConf(message['chat_id']):
            return
        if self.tm.isBusy(self.getSender(message)) and not self.tm.canTerminate(self.getSender(message)):
            return

        message['_method'] = method
        try:
            ans = gen_reply(message)
        except Exception as e:
            ans = None
            log.error('local {}: {}'.format(e.__class__.__name__, str(e)), True)
            time.sleep(1)
        if ans:
            self.replyMessage(message, ans[0], ans[1])

    def replyAll(self, gen_reply, include_read=False):
        self.tm.gc()
        self.banned_list = []
        if include_read:
            log.info('Include read')
            self.users.gc()
            messages = self.api.messages.getDialogs(unread=(0 if self.whitelist else 1), count=(20 if self.whitelist else 200))
            try:
                messages = messages['items'][::-1]
            except TypeError:
                log.warning('Unable to fetch messages')
                return
            self.loadUsers(messages, lambda x:x['message']['user_id'])
            self.loadUsers(messages, lambda x:x['message']['chat_id'], confs=True)
            for msg in sorted(messages, key=lambda msg:msg['message']['id']):
                cur = msg['message']
                if cur['out']:
                    continue
                if self.last_message_id and cur['id'] > self.last_message_id:
                    continue
                self.replyOne(cur, gen_reply, 'getDialogs')
            self.api.sync()
            stats.update('banned_messages', ' '.join(map(str, sorted(self.banned_list))))

        else:
            messages = self.longpollMessages()
            self.loadUsers(messages, lambda x:x['user_id'])
            self.loadUsers(messages, lambda x:x['chat_id'], confs=True)
            for cur in sorted(messages, key=lambda msg:msg['id']):
                self.last_message_id = max(self.last_message_id, cur['id'])
                self.replyOne(cur, gen_reply)
            self.api.sync()

    def longpollMessages(self):
        arr = self.api.getLongpoll()
        need_extra = []
        result = []
        for i in arr:
            if i[0] == 4:  # new message
                mid = i[1]
                sender = i[3]
                ts = i[4]
                text = i[6]
                opt = i[7]
                flags = i[2]
                if opt == {'source_mid': str(self.self_id), 'source_act': 'chat_kick_user', 'from': str(self.self_id)}:
                    self.good_conf[sender] = False
                    continue
                if opt.get('source_act') == 'chat_title_update':
                    del self.confs[sender - CONF_START]
                    log.info('Conf {} renamed into "{}"'.format(sender - CONF_START, opt['source_text']))
                    if self.bad_conf_title(opt['source_text']):
                        self.leaveConf(sender - CONF_START)
                        log.write('conf',  'conf ' + str(sender - CONF_START) + ' (name: {})'.format(opt['source_text']))
                        continue
                if opt.get('source_act') == 'chat_invite_user' and opt['source_mid'] == str(self.self_id) and opt['from'] != str(self.self_id):
                    self.logSender('%sender% added me to conf "{}"'.format(self.confs[sender - CONF_START]['title']), {'user_id': int(opt['from'])})
                    self.deleteFriend(int(opt['from']))
                    continue
                if flags & 2:  # out
                    continue
                for i in range(1, 11):
                    if opt.get('attach{}_type'.format(i)) == 'photo':
                        del opt['attach{}_type'.format(i)]
                        del opt['attach{}'.format(i)]
                        text += ' ..'
                    if opt.get('attach{}_type'.format(i)) == 'doc' and opt.get('attach{}_kind'.format(i)) == 'graffiti':
                        del opt['attach{}_type'.format(i)]
                        del opt['attach{}'.format(i)]
                        del opt['attach{}_kind'.format(i)]
                        text += ' ..'
                if  not (set(opt) <= {'from', 'emoji'} or opt.get('attach1_type') == 'sticker'):
                    need_extra.append(str(mid))
                    continue
                msg = {'id': mid, 'date': ts, 'body': text, 'out': 0, '_method': ''}
                if opt.get('attach1_type') == 'sticker':
                    msg['body'] = ''

                if 'from' in opt:
                    msg['chat_id'] = sender - CONF_START
                    msg['user_id'] = int(opt['from'])
                else:
                    msg['user_id'] = sender
                result.append(msg)

        if need_extra:
            need_extra = ','.join(need_extra)
            for i in self.api.messages.getById(message_ids=need_extra)['items']:
                i['_method'] = 'getById'
                result.append(i)
        return result

    def sendMessage(self, to, msg, resend=False):
        if not self.good_conf.get(to, 1):
            return
        with self.message_lock:
            self.guid += 1
            time.sleep(1)
            if resend:
                return self.api.messages.send(peer_id=to, forward_messages=msg, random_id=self.guid)
            else:
                return self.api.messages.send(peer_id=to, message=msg, random_id=self.guid)

    # fast==1: no delay
    #       2: no markAsRead
    def replyMessage(self, message, answer, fast=0):
        sender = self.getSender(message)
        sender_msg = self.last_message.bySender(sender)
        if 'id' in message and message['id'] <= sender_msg.get('id', 0):
            return

        if not answer:
            if self.tm.isBusy(sender):
                return
            if not sender_msg or time.time() - sender_msg['time'] > self.forget_interval:
                tl = Timeline().sleep(self.delay_on_first_reply).do(lambda:self.api.messages.markAsRead(peer_id=sender))
                self.tm.run(sender, tl, tl.terminate)
            elif answer is None:  # ignored
                self.api.messages.markAsRead.delayed(peer_id=sender)
            else:
                tl = Timeline().sleep((self.delay_on_reply - 1) * random.random() + 1).do(lambda:self.api.messages.markAsRead(peer_id=sender))
                self.tm.run(sender, tl, tl.terminate)
            self.last_message.byUser(message['user_id'])['text'] = message['body']
            self.last_message.updateTime(sender)
            return

        typing_time = 0
        if (fast == 0 or fast == 2) and not answer.startswith('&#'):
            typing_time = len(answer) / self.chars_per_second

        resend = False
        # answer is not empty
        if fast == 0 and sender_msg.get('reply', '').upper() == answer.upper() and sender_msg['user_id'] == message['user_id']:
            log.info('Resending')
            typing_time = 0
            resend = True

        def _send():
            try:
                if resend:
                    res = self.sendMessage(sender, sender_msg['id'], resend=True)
                else:
                    res = self.sendMessage(sender, answer)
                if res is None:
                    del self.users[sender]
                    text_msg = 'Failed to send a message to ' + self.printableSender(message, False)
                    html_msg = 'Failed to send a message to ' + self.printableSender(message, True)
                    log.info((text_msg, html_msg))
                    return
                self.last_message.add(sender, message, res, answer)
                if fast == 1:
                    self.last_message.updateTime(sender, 0)
            except Exception as e:
                log.error('thread {}: {}'.format(e.__class__.__name__, str(e)), True)

        cur_delay = (self.delay_on_reply - 1) * random.random() + 1
        send_time = cur_delay + typing_time
        user_delay = 0
        if sender_msg and sender != self.admin:
            user_delay = sender_msg['time'] - time.time() + (self.same_user_interval if sender < 2000000000 else self.same_conf_interval)  # can be negative
        tl = Timeline(max(send_time, user_delay))
        if not sender_msg or time.time() - sender_msg['time'] > self.forget_interval:
            if fast == 0:
                tl.sleep(self.delay_on_first_reply)
                tl.do(lambda:self.api.messages.markAsRead(peer_id=sender))
        else:
            tl.sleepUntil(send_time, (self.delay_on_reply - 1) * random.random() + 1)
            if fast == 0:
                tl.do(lambda:self.api.messages.markAsRead(peer_id=sender))

        if fast != 1:
            tl.sleep(cur_delay)
        if message.get('_onsend_actions'):
            for i in message['_onsend_actions']:
                tl.do(i)
                tl.sleep(cur_delay)
        if typing_time:
            tl.doEveryFor(self.typing_interval, lambda:self.api.messages.setActivity(type='typing', user_id=sender), typing_time)
        tl.do(_send)
        self.tm.run(sender, tl)

    def checkConf(self, cid):
        if cid + CONF_START in self.good_conf:
            return self.good_conf[cid + CONF_START]
        messages = self.api.messages.getHistory(chat_id=cid)['items']
        for i in messages:
            if i.get('action') == 'chat_create':
                self.leaveConf(cid)
                self.deleteFriend(i['user_id'])
                log.write('conf', self.loggableName(i.get('user_id')) + ' ' + str(cid))
                return False
        title = self.confs[cid]['title']
        if self.bad_conf_title(title):
            self.leaveConf(cid)
            log.write('conf',  'conf ' + str(cid) + ' (name: {})'.format(title))
            return False
        self.good_conf[cid + CONF_START] = True
        return True

    def leaveConf(self, cid):
        log.info('Leaving conf {} ("{}")'.format(cid, self.confs[cid]['title']))
        self.good_conf[cid + CONF_START] = False
        return self.api.messages.removeChatUser(chat_id=cid, user_id=self.self_id)

    def addFriends(self, gen_reply, is_good):
        data = self.api.friends.getRequests(extended=1)
        to_rep = []
        self.loadUsers(data['items'], lambda x:x['user_id'], True)
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

    def unfollow(self, banned):
        result = []
        requests = self.api.friends.getRequests(out=1)['items'] + self.api.friends.getRequests(suggested=1)['items']
        for i in requests:
            if i not in banned:
                self.api.friends.delete.delayed(user_id=i)
                result.append(i)
        self.api.sync()
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

    def getUserId(self, domain):
        domain = str(domain).lower().rstrip().rstrip('}').rstrip()
        conf = re.search('sel=c(\\d+)', domain) or re.search('^c(\\d+)$', domain) or re.search('chat=(\\d+)', domain) or re.search('peer=2(\\d{9})', domain)
        if conf is not None:
            return int(conf.group(1)) + CONF_START
        if '=' in domain:
            domain = domain.split('=')[-1]
        if '/' in domain:
            domain = domain.split('/')[-1]
        data = self.api.users.get(user_ids=domain)
        if not data:
            return None
        return data[0]['id']


    def deleteComment(self, rep):
        if rep['type'].endswith('photo'):
            self.api.photos.deleteComment(owner_id=self.self_id, comment_id=rep['feedback']['id'])
        elif rep['type'].endswith('video'):
            self.api.video.deleteComment(owner_id=self.self_id, comment_id=rep['feedback']['id'])
        else:
            self.api.wall.deleteComment(owner_id=self.self_id, comment_id=rep['feedback']['id'])

    def filterComments(self, test):
        data = self.api.notifications.get(start_time=self.last_viewed_comment+1, count=100)['items']
        to_del = set()
        to_bl = set()
        self.loadUsers(data, lambda x:x['feedback']['from_id'], True)
        for rep in data:
            if rep['date'] != 'i':
                self.last_viewed_comment = max(self.last_viewed_comment, int(rep['date']))
                stats.update('last_comment', self.last_viewed_comment)

            def _check(s):
                if 'photo' in s:
                    return s['photo']['owner_id'] == self.self_id
                if 'video' in s:
                    return s['video']['owner_id'] == self.self_id
                if 'post' in s:
                    return s['post']['to_id'] == self.self_id

            if rep['type'].startswith('comment_') or rep['type'].startswith('reply_comment') and _check(rep['parent']):
                txt = html.escape(rep['feedback']['text'])
                res = 'good'
                if self.users[rep['feedback']['from_id']]['blacklisted']:
                    res = 'blacklisted'
                    log.write('comments', self.loggableName(rep['feedback']['from_id']) + ' (blacklisted): ' + txt)
                    self.deleteComment(rep)
                    to_bl.add(rep['feedback']['from_id'])
                elif test(txt):
                    res = 'bad'
                    log.write('comments', self.loggableName(rep['feedback']['from_id']) + ': ' + txt)
                    self.deleteComment(rep)
                    to_del.add(rep['feedback']['from_id'])
                elif 'attachments' in rep['feedback'] and  any(i.get('type') in ['video', 'link', 'doc', 'sticker'] for i in rep['feedback']['attachments']):
                    res = 'attachment'
                    log.write('comments', self.loggableName(rep['feedback']['from_id']) + ' (attachment)')
                    self.deleteComment(rep)
                self.logSender('Comment {} (by %sender%) - {}'.format(txt, res), {'user_id':rep['feedback']['from_id']})
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
        self.api.account.saveProfileInfo(relation_partner_id=uid)
        self.bf = self.users[uid]
        log.write('relation', self.loggableName(uid))
        self.logSender('Set relationship with %sender%', {'user_id': uid})

    def waitAllThreads(self):
        for t in self.tm.all():
            t.join(60)

    # {name} - first_name last_name
    # {id} - id
    def printableName(self, pid, user_fmt, conf_fmt='Conf "{name}"'):
        if pid > CONF_START:
            return conf_fmt.format(id=(pid - CONF_START), name=self.confs[pid - CONF_START]['title'])
        else:
            return user_fmt.format(id=(pid), name=self.users[pid]['first_name'] + ' ' + self.users[pid]['last_name'])

    def logSender(self, text, message):
        text_msg = text.replace('%sender%', self.printableSender(message, False))
        html_msg = text.replace('%sender%', self.printableSender(message, True))
        log.info((text_msg, html_msg))

    def printableSender(self, message, need_html):
        if message.get('chat_id', 0) > 0:
            if need_html:
                return self.printableName(message['user_id'], user_fmt='Conf "%c", <a href="https://vk.com/id{id}" target="_blank">{name}</a>').replace('%c', html.escape(self.confs[message['chat_id']]['title']))
            else:
                return self.printableName(message['user_id'], user_fmt='Conf "%c", {name}').replace('%c', html.escape(self.confs[message['chat_id']]['title']))
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
        for i in dialogs['items']:
            self.api.messages.getHistory.delayed(peer_id=self.getSender(i['message']), count=0).callback(cb)
            if 'title' in i['message']:
                confs[self.getSender(i['message'])] = i['message']['title']
        self.api.sync()
        return (dialogs['count'], d, confs)
