import logging

import accounts
import cppbot
import log

need_auth = True


def isBad(bot, comm):
    return bot.interact('comm ' + bot.escape(comm)) == '$blacklisted'

# noinspection PyUnusedLocal
def main(a, args):
    a.timeout = 10

    bot = cppbot.CppBot('', 0, None)
    self_id = a.users.get()[0]['id']

    def wall_cb(req, resp):
        for post in resp['items']:
            a.wall.getComments.walk(post_cb, post_id=post['id'], count=100)

    def post_cb(req, resp):
        for comm in resp['items']:
            if comm['from_id'] != self_id and comm.get('text') and isBad(bot, comm['text']):
                a.wall.deleteComment.delayed(comment_id=comm['id'])
                log.write('_delcomments', '{}: {}'.format(comm['from_id'], comm['text']))


    a.wall.get.walk(wall_cb, count=100, filter='others').sync()
