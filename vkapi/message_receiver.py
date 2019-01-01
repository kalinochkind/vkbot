import html
import logging
import queue
import threading
import time

from .incoming_message import IncomingMessage
from .utils import CONF_START, LongpollMessage

logger = logging.getLogger('vkapi.receiver')

class MessageReceiver:
    def __init__(self, api, get_dialogs_interval=-1, message_class=IncomingMessage):
        self.api = api
        self.get_dialogs_interval = get_dialogs_interval
        self.longpoll_queue = queue.Queue()
        self.longpoll_thread = threading.Thread(target=self.monitor, daemon=True)
        self.longpoll_thread.start()
        self.longpoll_callback = None
        self.last_message_id = 0
        self.last_get_dialogs = 0
        self.longpolled_messages = set()
        self.terminate_monitor = False
        self.message_class = message_class


    def monitor(self):
        while True:
            try:
                for i in self._getLongpoll():
                    self.longpoll_queue.put(i)
            except Exception:
                logger.exception('MessageReceiver error')
                time.sleep(5)

    def getMessages(self, get_dialogs=False):
        ctime = time.time()
        if not self.last_get_dialogs:
            self.last_get_dialogs = ctime - self.get_dialogs_interval + 1
        if (self.get_dialogs_interval >=0 and ctime - self.last_get_dialogs > self.get_dialogs_interval) or get_dialogs:
            self.last_get_dialogs = ctime
            res = []
            messages = self.api.messages.getDialogs(unread=1, count=200)
            try:
                messages = messages['items'][::-1]
            except TypeError:
                logger.warning('Unable to fetch messages')
                return []
            for msg in sorted(messages, key=lambda m: m['message']['id']):
                cur = msg['message']
                if cur['out'] or cur['id'] in self.longpolled_messages:
                    continue
                if self.last_message_id and cur['id'] > self.last_message_id:
                    continue  # wtf?
                res.append(self.message_class(cur, method='getDialogs'))
            self.longpolled_messages.clear()
        else:
            res = []
            while not self.longpoll_queue.empty():
                res.append(self.longpoll_queue.get())
            res.sort(key=lambda x: x.id)
            self.longpolled_messages.update(i.id for i in res)
            if res:
                self.last_message_id = max(self.last_message_id, res[-1].id)
        return res

    def _getLongpoll(self):
        arr = self.api.getLongpoll()
        if self.terminate_monitor:
            return []
        need_extra = []
        result = []
        for record in arr:
            if record[0] == 4:  # new message
                lm = LongpollMessage(record[1:])
                if self.longpoll_callback and self.longpoll_callback(lm):
                    continue

                if lm.flags & 2:
                    continue
                msg = {'id': lm.mid, 'date': lm.ts, 'body': html.unescape(lm.text).replace('<br>', '\n'), 'out': 0, '_method': ''}
                if lm.opt.get('source_act'):
                    msg['body'] = None
                    msg['action'] = lm.opt['source_act']
                if 'from' in lm.opt:
                    msg['chat_id'] = lm.sender - CONF_START
                    msg['user_id'] = int(lm.opt['from'])
                else:
                    msg['user_id'] = lm.sender

                attachments = []
                for number in range(1, 11):
                    prefix = 'attach' + str(number)
                    kind = lm.extra.get(prefix + '_type')
                    if kind is None:
                        continue  # or break
                    if kind == 'photo':
                        attachments.append({'type': 'photo'})
                    elif kind == 'sticker':
                        attachments.append({'type': 'sticker'})
                    elif kind == 'doc' and lm.extra.get(prefix + '_kind') == 'audiomsg':
                        attachments.append({'type': 'doc', 'doc': {'type': 5}})
                    elif kind == 'doc' and lm.extra.get(prefix + '_kind') == 'graffiti':
                        attachments.append({'type': 'doc', 'doc': {'type': 4, 'graffiti': None}})
                    elif kind == 'call':
                        attachments.append({'type': 'call'})
                    else:  # something hard
                        need_extra.append(str(lm.mid))
                        msg = None
                        break
                if not msg:
                    continue
                if attachments:
                    msg['attachments'] = attachments
                for i in list(lm.extra):
                    if i.startswith('attach'):
                        del lm.extra[i]
                if not set(lm.extra) <= {'emoji'} and not lm.extra.get('source_act'):
                    need_extra.append(str(lm.mid))
                    continue
                result.append(self.message_class(msg, method='longpoll'))

        if need_extra:
            need_extra = ','.join(need_extra)
            for i in self.api.messages.getById(message_ids=need_extra)['items']:
                result.append(self.message_class(i, method='getById'))
        return result
