import vkapi
import time
import log
from thread_manager import thread_manager, timeline
from user_cache import user_cache
import config
import re
import random

CONF_START = 2000000000

class vk_bot:

    delay_on_reply = config.get('vkbot.delay_on_reply')
    chars_per_second = config.get('vkbot.chars_per_second')
    same_user_interval = config.get('vkbot.same_user_interval')
    same_conf_interval = config.get('vkbot.same_conf_interval')
    typing_interval = config.get('vkbot.typing_interval')
    noans = open('noans.txt').read().split()

    def __init__(self, username, password, captcha_handler=None):
        self.api = vkapi.vk_api(username, password, captcha_handler=captcha_handler)
        self.api.initLongpoll()
        self.users = user_cache(self.api, 'sex,photo_id,blacklisted,blacklisted_by_me')
        self.initSelf()
        self.guid = int(time.time() * 5)

        self.last_viewed_comment = 0
        self.banned_messages = set()
        self.good_conf = {}
        self.tm = thread_manager()
        self.last_message = {}
        self.last_message_id = 0

    def initSelf(self):
        self.users.clear()
        res = self.api.users.get(fields='contacts')[0]
        self.self_id = res['id']
        self.phone = res.get('mobile_phone', '')
        print('My phone:', self.phone)


    def replyAll(self, gen_reply, include_read=0):
        self.tm.gc()
        if include_read:
            print('Include read')
            try:
                messages = self.api.messages.getDialogs(unread=1, count=200)['items'][::-1]
            except KeyError:
                # may sometimes happen because of friendship requests
                return
            with self.api.api_lock:
                for i in sorted(messages, key=lambda x:x['message']['id']):
                    cur = i['message']
                    if self.last_message_id and cur['id'] > self.last_message_id:
                        continue
                    if 'chat_id' in cur:
                        if not self.checkConf(cur['chat_id']):
                            continue
                    if self.tm.isBusy(self.getSender(cur)):
                        continue
                    cur['_method'] = 'getDialogs'
                    try:
                        ans = gen_reply(cur)
                    except Exception as e:
                        ans = None
                        print('[ERROR] %s: %s' % (e.__class__.__name__, str(e)))
                        time.sleep(1)
                    if not ans:
                        continue
                    self.replyMessage(cur, ans[0], ans[1])
                self.api.sync()
        else:
            messages = self.longpollMessages()
            with self.api.api_lock:
                for cur in sorted(messages, key=lambda x:x['id']):
                    self.last_message_id = max(self.last_message_id, cur['id'])
                    if 'chat_id' in cur:
                        if not self.checkConf(cur['chat_id']):
                            continue
                    if self.tm.isBusy(self.getSender(cur)):
                        continue
                    try:
                        ans = gen_reply(cur)
                    except Exception as e:
                        ans = None
                        print('[ERROR] %s: %s' % (e.__class__.__name__, str(e)))
                        time.sleep(1)
                    if not ans:
                        continue
                    self.replyMessage(cur, ans[0], ans[1])
                self.api.sync()
            
        
    def longpollMessages(self):
        arr = self.api.getLongpoll()
        need_extra = []
        for i in arr:
            if i[0] == 51:  # conf params changed
                pass  # TODO
            if i[0] == 4:  # new message
                mid = i[1]
                sender = i[3]
                ts = i[4]
                text = i[6]
                opt = i[7]
                flags = i[2]
                if flags & 2:  # out
                    continue
                for i in range(1, 11):
                    if opt.get('attach{}_type'.format(i)) == 'photo':
                        del opt['attach{}_type'.format(i)]
                        del opt['attach{}'.format(i)]
                        text += '.. '
                if  not (set(opt) <= {'from', 'emoji'} or opt.get('attach1_type') == 'sticker'):
                    need_extra.append(str(mid))
                    continue
                msg = {'id': mid, 'date': ts, 'body': text, 'out': 0, '_method': ''}
                if opt.get('attach1_type') == 'sticker':
                    msg['body'] = '...'
                if 'from' in opt:
                    msg['chat_id'] = sender - 2000000000
                    msg['user_id'] = opt['from']
                else:
                    msg['user_id'] = sender
                yield msg
        if need_extra:
            need_extra = ','.join(need_extra)
            for i in self.api.messages.getById(message_ids=need_extra)['items']:
                i['_method'] = 'getById'
                yield i
                

    def getSender(self, message):
        if 'chat_id' in message:
            return 2000000000 + message['chat_id']
        return message['user_id']

    def sendMessage(self, to, msg):
        if not self.good_conf.get(to, 1):
            return
        self.guid += 1
        return self.api.messages.send(peer_id=to, message=msg, guid=self.guid)

    # message==None: special conf messages, don't need to reply
    # fast==1: no delay
    #       2: no markAsRead
    def replyMessage(self, message, answer, fast=0):
        sender = self.getSender(message)
        if 'id' in message and message['id'] <= self.last_message.get(sender, (0, 0))[0]:
            return

        if answer == '$noans':
            if sender > 2000000000:
                answer = ''
            else:
                answer = random.choice(self.noans)
        elif answer == '$blacklisted':
            answer = ''

        if not answer:
            if 'id' in message:
                self.banned_messages.add(message['id'])
                self.api.messages.markAsRead.delayed(peer_id=sender)
            return
        typing_time = 0
        if (fast == 0 or fast == 2) and not answer.startswith('&#'):
            typing_time = len(answer) / self.chars_per_second

        def _send():
            res = self.sendMessage(sender, answer)
            if res is None:
                log.write('bannedmsg', str(message['id']))  # not thread-safe, but who gives a fuck
                self.banned_messages.add(message['id'])
                return
            self.last_message[sender] = (res, 0 if fast == 1 else time.time())

        if fast == 0:
            pre_proc = lambda:self.api.messages.markAsRead(peer_id=sender)
        else:
            pre_proc = lambda:None
        typing_proc = lambda:self.api.messages.setActivity(type='typing', user_id=sender)

        send_time = self.delay_on_reply + typing_time
        user_delay = 0
        if sender in self.last_message:
            user_delay = self.last_message[sender][1] - time.time() + (self.same_user_interval if sender < 2000000000 else self.same_conf_interval)  # can be negative

        tl = timeline(max(send_time, user_delay))
        if tl.duration == send_time:
            if fast == 0:
                self.api.messages.markAsRead.delayed(peer_id=sender)
        else:
            tl.sleep_until(send_time).do(pre_proc)
        tl.sleep(self.delay_on_reply)
        if typing_time:
            tl.do_every_for(self.typing_interval, typing_proc, typing_time)
        tl.do(_send)
        self.tm.run(sender, tl)

    def checkConf(self, cid):
        if cid + CONF_START in self.good_conf:
            return self.good_conf[cid + CONF_START]
        messages = self.api.messages.getHistory(chat_id=cid)['items']
        for i in messages:
            if i.get('action') == 'chat_create':
                self.leaveConf(cid)
                log.write('conf', str(i.get('user_id')) + ' ' + str(cid))
                self.good_conf[cid + CONF_START] = 0
                return 0
        self.good_conf[cid + CONF_START] = 1
        return 1
    
    def leaveConf(self, cid):
        print('Leaving conf', cid)
        self.good_conf[cid + CONF_START] = 0
        return self.api.messages.removeChatUser(chat_id=cid, user_id=self.self_id)

    def addFriends(self, gen_reply, is_good):
        data = self.api.friends.getRequests(extended=1)
        self.api.delayedReset()
        to_rep = []
        for i in data['items']:
            if is_good(i['user_id']):
                self.api.friends.add.delayed(user_id=i['user_id'])
                if 'message' in i:
                    ans = gen_reply(i)
                    to_rep.append((i, ans))
            else:
                self.api.friends.delete.delayed(user_id=i['user_id'])
        for i in to_rep:
            self.replyMessage(i[0], i[1][0], i[1][1])
        self.api.sync()

    def unfollow(self, banned):
        requests = self.api.friends.getRequests(out=1)['items']
        self.api.delayedReset()
        for i in requests:
            if i not in banned:
                self.api.friends.delete.delayed(user_id=i)
        self.api.sync()
        return len(requests)

    def deleteFriend(self, uid):
        if type(uid) == int:
            self.api.friends.delete(user_id=uid)
        else:
            self.api.delayedReset()
            for i in uid:
                self.api.friends.delete.delayed(user_id=i)
            self.api.sync()

    def setOnline(self):
        self.api.account.setOnline(voip=0)

    def getUserId(self, domain):
        multiple = type(domain) != str
        if not multiple:
            domain = [domain]
        req = []
        for i in domain:
            i = str(i).rstrip().rstrip('}').rstrip()  # if id is in a forwarded message
            conf = re.search('sel=c(\\d+)', i) or re.search('^c(\\d+)$', i) or re.search('chat=(\\d+)', i) or re.search('peer=2(\\d{9})', i)
            if conf is not None:
                req.append(int(conf.group(1)) + 2000000000)
            else:
                if '=' in i:
                    i = i.split('=')[-1]
                if '/' in i:
                    i = i.split('/')[-1]
                req.append(int(i) if i.isdigit() else i)

        data = self.api.users.get(user_ids=','.join(i for i in req if type(i) == str))
        for i in range(len(req)):
            if type(req[i]) == str:
                req[i] = data[0]['id']
                data = data[1:]
        try:
            if multiple:
                return [str(i) for i in req]
            else:
                return str(req[0])
        except TypeError:
            return None
        
    def filterComments(self, test):
        data = self.api.notifications.get(start_time=self.last_viewed_comment+1)['items']
        for rep in data:
            self.last_viewed_comment = max(self.last_viewed_comment, rep['date'])
            
            def _check(s):
                if 'photo' in s:
                    return s['photo']['owner_id'] == self.self_id
                if 'video' in s:
                    return s['video']['owner_id'] == self.self_id
                if 'post' in s:
                    return s['post']['to_id'] == self.self_id
            
            if rep['type'].startswith('comment_') or rep['type'].startswith('reply_comment') and _check(rep['parent']):
                txt = rep['feedback']['text']
                if test(txt):
                    log.write('comments', str(rep['feedback']['from_id']) + ': ' + txt)
                    if rep['type'].endswith('photo'):
                        print('Deleting photo comment')
                        self.api.photos.deleteComment(owner_id=self.self_id, comment_id=rep['feedback']['id'])
                    elif rep['type'].endswith('video'):
                        print('Deleting video comment')
                        self.api.video.deleteComment(owner_id=self.self_id, comment_id=rep['feedback']['id'])
                    else:
                        print('Deleting wall comment')
                        self.api.wall.deleteComment(owner_id=self.self_id, comment_id=rep['feedback']['id'])
                        
    def likeAva(self, uid):
        try:
            photo = self.users[uid]['photo_id'].split('_')
            log.write('likeava', str(uid))
            self.api.likes.add(type='photo', owner_id=photo[0], item_id=photo[1])
        except Exception:
            log.write('likeava', str(uid) + ' failed')

    def setRelation(self, uid):
        try:
            self.api.account.saveProfileInfo(relation_partner_id=uid)
            log.write('relation', uid)
        except Exception:
            log.write('relation', str(uid) + ' failed')
