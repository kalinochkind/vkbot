import enum

from vkapi.utils import getSender, CONF_START


class ResponseType(enum.Enum):
    NO_READ = 0
    IGNORE = 1
    NO_RESPONSE = 2
    TEXT = 3
    STICKER = 4


class BotResponse:
    def __init__(self, message, type, data=None, onsend_actions=()):
        self.type = type
        self.user_id = message['user_id']
        self.sender_id = getSender(message)
        self.message_body = message.get('body')
        self.message_id = message['id']
        self.message_has_action = 'action' in message
        self.data = data
        self.onsend_actions = list(onsend_actions)
        self.text = self.data if self.type == ResponseType.TEXT else ''

    def fake_message(self):
        if self.sender_id == self.user_id:
            return {'user_id': self.user_id}
        else:
            return {'user_id': self.user_id, 'chat_id': self.sender_id - CONF_START}

    @property
    def is_chat(self):
        return self.sender_id > CONF_START
