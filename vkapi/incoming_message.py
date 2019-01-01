from .utils import CONF_START, doc_types, cached_property


class IncomingMessage:

    def __init__(self, data, method=''):
        self.id = data.get('id')
        self.date = data['date']
        self.body = data.get('body', '')
        self.user_id = data['user_id']
        self.chat_id = data.get('chat_id')
        self.action = data.get('action')
        self.attachments = data.get('attachments', [])
        self._fwd_messages_raw = data.get('fwd_messages', [])
        self.method = method

        self.is_sticker = False
        self.is_voice = False
        for att in self.attachments:
            if att['type'] == 'sticker':
                self.is_sticker = True
            if att['type'] == 'doc' and att['doc']['type'] == doc_types.AUDIO:
                self.is_voice = True

    def _construct_forwarded_message(self, data):
        return self.__class__(data)

    @property
    def peer_id(self):
        if self.chat_id is not None:
            return CONF_START + self.chat_id
        return self.user_id

    @property
    def is_chat(self):
        return self.chat_id is not None

    @cached_property
    def fwd_messages(self):
        fwd_messages = [self._construct_forwarded_message(data) for data in self._fwd_messages_raw]
        del self._fwd_messages_raw
        return fwd_messages
