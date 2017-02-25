TYPING_INTERVAL = 5
CONF_START = 2000000000


class DelayedCall:
    def __init__(self, method, params):
        self.method = method
        self.params = params
        self.retry = False
        self.callback_func = None

    def callback(self, func):
        self.callback_func = func
        return self

    def called(self, response):
        if self.callback_func:
            self.callback_func(self.params, response)

    def __eq__(self, a):
        return self.method == a.method and self.params == a.params and self.callback_func is None and a.callback_func is None

class VkError(Exception):
    pass

def getSender(message):
    if 'chat_id' in message:
        return CONF_START + message['chat_id']
    return message['user_id']
