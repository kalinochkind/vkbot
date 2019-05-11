import logging
import urllib.request

logger = logging.getLogger('voice')

class VoiceRecognizer:

    def __init__(self, wit_token):
        from wit import Wit
        self.wit = Wit(wit_token)

    def get_text(self, mp3_link):
        from wit.wit import WitError
        logger.info('Recognizing voice message')
        try:
            with urllib.request.urlopen(mp3_link) as f:
                return self.wit.speech(f, None, {'Content-type': 'audio/mpeg'})['_text']
        except WitError:
            logger.warning('Wit error')
            return None
