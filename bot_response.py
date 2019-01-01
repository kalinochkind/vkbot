import enum

from vkapi.utils import CONF_START
from vkbot_message import PeerInfo


class ResponseType(enum.Enum):
    NO_READ = 0
    IGNORE = 1
    NO_RESPONSE = 2
    TEXT = 3
    STICKER = 4


class BotResponse:
    def __init__(self, message, type, data=None, onsend_actions=()):
        self.type = type
        self.user_id = message.user_id
        self.peer_id = message.peer_id
        self.message_body = message.body
        self.message_id = message.id
        self.message_has_action = bool(message.action)
        self.data = data
        self.onsend_actions = list(onsend_actions)

    def fake_message(self):
        if self.peer_id == self.user_id:
            return {'user_id': self.user_id}
        else:
            return {'user_id': self.user_id, 'chat_id': self.peer_id - CONF_START}

    @property
    def is_chat(self):
        return self.peer_id > CONF_START

    @property
    def text(self):
        return self.data if self.type == ResponseType.TEXT else ''

    def get_peer_info(self):
        if self.peer_id == self.user_id:
            return PeerInfo(self.user_id)
        return PeerInfo(self.user_id, self.peer_id - CONF_START)
