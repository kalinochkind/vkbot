import vkapi
import time
import log
from thread_manager import thread_manager
import config

class vk_bot:

    delay_on_reply = config.get('vkbot.delay_on_reply')
    chars_per_second = config.get('vkbot.chars_per_second')
    same_user_interval = config.get('vkbot.same_user_interval')
    same_conf_interval = config.get('vkbot.same_conf_interval')

    def __init__(self, username, password, captcha_handler=None):
        self.api = vkapi.vk_api(username, password)
        self.api.captcha_handler = captcha_handler
        self.api.getToken()
        self.banned_messages = set()
        self.guid = int(time.time() * 5)
        self.ensureLoggedIn()
        self.self_id = str(self.api.users.get()[0]['id'])
        self.last_viewed_comment = 0
        self.name_cache = {}
        self.good_conf = set()
        self.tm = thread_manager()
        self.last_message = {}
        self.left_confs = set()
        self.last_message_id = 0
        self.api.initLongpoll()

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
                if  not (set(opt) <= {'from', 'emoji'}):
                    need_extra.append(str(mid))
                    continue
                msg = {'id': mid, 'date': ts, 'body': text, 'out': 0, '_method': ''}
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
            return str(2000000000 + int(message['chat_id']))
        return str(message['user_id'])

    def sendMessage(self, to, msg):
        if int(to) in self.left_confs:
            return
        self.guid += 1
        return self.api.messages.send(peer_id=to, message=msg, guid=self.guid)

    # message==None: special conf messages, don't need to reply
    # fast==1: no delay
    #       2: no markAsRead
    def replyMessage(self, message, answer, fast=0):
        sender = self.getSender(message)
        if int(message['id']) <= self.last_message.get(sender, (0, 0))[0]:
            return
        if fast == 0:
            self.api.messages.markAsRead.delayed(message_ids=message['id'])
        if not answer:
            self.banned_messages.add(message['id'])
            return
        delayed = 0
        if fast == 0 or fast == 2:
            delayed = len(answer) / self.chars_per_second
        def _send():
            res = self.sendMessage(sender, answer)
            if res is None:
                log.write('bannedmsg', str(message['id']))  # not thread-safe, but who gives a fuck
                self.banned_messages.add(message['id'])
                return
            self.last_message[sender] = (int(res), time.time())
#            self.last_message_id[sender] = int(res)
        if answer.startswith('&#'):
            self.tm.run(sender, _send, delayed, self.delay_on_reply, 0, None, self.last_message.get(sender, (0, 0))[1] - time.time() + (self.same_user_interval if int(sender) < 2000000000 else self.same_conf_interval))
        else:
            self.tm.run(sender, _send, delayed, self.delay_on_reply, 8, lambda:self.api.messages.setActivity(type='typing', user_id=sender), self.last_message.get(sender, (0, 0))[1] - time.time() + (self.same_user_interval if int(sender) < 2000000000 else self.same_conf_interval))  # AAAAAAAA 

    def checkConf(self, cid):
        cid = str(cid)
        if cid in self.good_conf:
            return 1
        messages = self.api.messages.getHistory(chat_id=cid)['items']
        for i in messages:
            if i.get('action') == 'chat_create':
                self.leaveConf(cid)
                log.write('conf', cid)
                return 0
        self.good_conf.add(cid)
        return 1
    
    def leaveConf(self, cid):
        print('Leaving conf', cid)
        self.left_confs.add(2000000000 + int(cid))
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
        self.api.sync()
        for i in to_rep:
            self.replyMessage(i[0], i[1][0], i[1][1])

    def unfollow(self, banned):
        requests = self.api.friends.getRequests(out=1)['items']
        self.api.delayedReset()
        for i in requests:
            if str(i) not in banned:
                self.api.friends.delete.delayed(user_id=i)
        self.api.sync()
        return len(requests)

    def setOnline(self):
        self.api.account.setOnline(voip=0)

    def getUserId(self, uid):
        if uid.isdigit():
            return uid
        if '=' in uid:
            uid = uid.split('=')[-1]
        if '/' in uid:
            uid = uid.split('/')[-1]
        data = self.api.users.get(user_ids=uid)
        try:
            return str(data[0]['id'])
        except TypeError:
            return None
    
    def ensureLoggedIn(self):
        self.api.account.getCounters()
        
    def getUserInfo(self, uid):
        uid = str(uid)
        if uid not in self.name_cache:    
            r = self.api.users.get(user_ids=uid, fields='sex,photo_id')[0]
            self.name_cache[uid] = r
        return self.name_cache[uid]
        
    def filterComments(self, test):
        data = self.api.notifications.get(start_time=self.last_viewed_comment+1)['items']
        for rep in data:
            self.last_viewed_comment = max(self.last_viewed_comment, rep['date'])
            
            def _check(s):
                if 'photo' in s:
                    return str(s['photo']['owner_id']) == self.self_id
                if 'video' in s:
                    return str(s['video']['owner_id']) == self.self_id
                if 'post' in s:
                    return str(s['post']['to_id']) == self.self_id
            
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
            photo = self.getUserInfo(uid)['photo_id'].split('_')
            log.write('likeava', str(uid))
            self.api.likes.add(type='photo', owner_id=photo[0], item_id=photo[1])
        except Exception:
            log.write('likeava', str(uid) + ' failed')
