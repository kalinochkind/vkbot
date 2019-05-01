import logging
import urllib.request

logger = logging.getLogger('voice')

class VoiceRecognizer:

    def __init__(self, wit_token):
        from wit import Wit
        self.wit = Wit(wit_token)

    def get_text(self, mp3_link):
        from wit.wit import WitError
        try:
            logger.info('Recognizing voice message')
            for i in range(3):
                try:
                    with urllib.request.urlopen(mp3_link) as f:
                        return self.wit.speech(f, None, {'Content-type': 'audio/mpeg'})['_text']
                except WitError:
                    if i == 2:
                        raise
                    logger.warning('Wit error, retrying')
        except Exception:
            logger.exception('Voice recognition error')
            return None

