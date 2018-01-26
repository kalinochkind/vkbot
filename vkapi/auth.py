import urllib.request
import urllib.parse
import urllib.error
from http.cookiejar import CookieJar
import re
import logging


FORM_ELEMENT = re.compile(r'<input type="hidden" name="([^"]+)" value="([^"]+)"')
ACCESS_TOKEN = re.compile(r'access_token=([0-9a-f]+)($|&)')

logger = logging.getLogger('vkapi.auth')

def login(username, password, client_id, perms):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    url = ('https://oauth.vk.com/authorize?redirect_uri=https://oauth.vk.com/blank.html&'
           'client_id={}&scope={}&response_type=token&display=mobile'.format(client_id, perms))
    try:
        auth_page = opener.open(url)
    except urllib.error.HTTPError as e:
        logger.exception(e)
        print(url)
        return None
    auth_page = auth_page.read().decode()
    fields = dict(FORM_ELEMENT.findall(auth_page))
    fields['email'], fields['pass'] = username, password
    token_url = opener.open('https://login.vk.com/?act=login&soft=1&utf8=1', 
                            data=urllib.parse.urlencode(fields).encode()).geturl()
    match = ACCESS_TOKEN.search(token_url)
    if match:
        return match.group(1)
    else:
        print(url)
        return None


class perms:
    NOTIFY = 1
    FRIENDS = 2
    PHOTOS = 4
    AUDIO = 8
    VIDEO = 16
    APP_WIDGET = 64
    PAGES = 128
    STATUS = 1024
    NOTES = 2048
    MESSAGES = 4096
    WALL = 8192
    ADS = 32768
    OFFLINE = 65536
    DOCS = 131072
    GROUPS = 262144
    MANAGE = 262144
    NOTIFICATIONS = 524288
    STATS = 1048576
    EMAIL = 4194304
    MARKET = 134217728
