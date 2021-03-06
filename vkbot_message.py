import re

import config
from vkapi.incoming_message import IncomingMessage
from vkapi.utils import cached_property, doc_types, CONF_START

STARTS_WITH_URL_RE = re.compile('(https?://)?[a-z0-9\-]+\.[a-z0-9\-]+')


class VkbotMessage(IncomingMessage):

    VOICE_FALLBACK = 'voice'

    def __init__(self, *args, self_id=None, voice_recognizer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.self_id = self_id
        self.voice_recognizer = voice_recognizer

    def _construct_forwarded_message(self, data):
        return self.__class__(data, self_id=self.self_id)

    def _get_voice_content(self, voice):
        if self.voice_recognizer is None or 'link_mp3' not in voice:
            return self.VOICE_FALLBACK
        text = self.voice_recognizer.get_text(voice['link_mp3'])
        return text if text is not None else self.VOICE_FALLBACK

    def _process_body(self, toplevel=False):
        if self.is_my_message:
            return ''
        if self.action:
            return None

        result = self.body
        att = []
        for a in self.attachments:
            if a['type'] == 'audio':
                if not config.get('vkbot.ignore_audio', 'b'):
                    att.append(a['audio']['title'])
            elif a['type'] == 'video':
                att.append(a['video']['title'])
            elif a['type'] == 'wall':
                att.append(a['wall']['text'])
                if not a['wall']['text'] and 'copy_history' in a['wall']:
                    att[-1] = a['wall']['copy_history'][0]['text']
            elif a['type'] == 'doc':
                att.append(a['doc']['title'])
            elif a['type'] == 'audio_message':
                if toplevel:
                    att.append(self._get_voice_content(a['audio_message']))
                else:
                    att.append(self.VOICE_FALLBACK)
            elif a['type'] == 'gift':
                att.append('vkgift')
            elif a['type'] == 'link':
                att.append(a['link']['title'] + ': ' + a['link']['description'])
            elif a['type'] == 'market':
                att.append(a['market']['description'])
            elif a['type'] == 'sticker':
                att.append('sticker')
            elif a['type'] == 'photo' or a['type'] == 'graffiti':
                result += ' ..'
            elif a['type'] == 'call':
                return None
        for a in att:
            result += ' [' + a + ']'

        if self.fwd_messages:
            fwd_users = {fwd.user_id for fwd in self.fwd_messages}
            if fwd_users in ({self.self_id}, {self.user_id, self.self_id}):
                return result.strip() + ' ' + '{}' * len(self.fwd_messages)
            elif fwd_users == {self.user_id}:
                for fwd in self.fwd_messages:
                    r = fwd._process_body()
                    if r is None:
                        return None
                    result += ' {' + r.strip() + '}'
            else:
                return None

        return result.strip()

    @property
    def is_my_message(self):
        return self.user_id == self.self_id

    @cached_property
    def processed_body(self):
        return self._process_body(True)

    def get_answer_case(self):
        text = self.body
        if text != text.lower():
            return 'normal'
        if not text or not text[0].isalpha() or STARTS_WITH_URL_RE.match(text):
            return None
        return 'lower'

    def get_peer_info(self):
        return PeerInfo(self.user_id, self.chat_id)


class PeerInfo:

    def __init__(self, user_id, chat_id=None):
        self.user_id = user_id
        self.chat_id = chat_id

    @property
    def peer_id(self):
        if self.chat_id is not None:
            return CONF_START + self.chat_id
        return self.user_id

    @property
    def is_chat(self):
        return self.chat_id is not None
