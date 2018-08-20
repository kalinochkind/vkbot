import logging

import accounts
import cppbot
import log


def isBad(bot, comm):
    return bot.interact('comm ' + bot.escape(comm)) == '$blacklisted'

# noinspection PyUnusedLocal
def main(a, args):
    a.timeout = 10

    dm = a.delayed()

    bot = cppbot.CppBot('', 0, None)
    self_id = a.users.get()[0]['id']

    def wall_cb(req, resp):
        for post in resp['items']:
            dm.wall.getComments(post_id=post['id'], count=100).walk(post_cb)

    def post_cb(req, resp):
        for comm in resp['items']:
            if comm['from_id'] != self_id and comm.get('text') and isBad(bot, comm['text']):
                dm.wall.deleteComment(comment_id=comm['id'])
                log.write('_delcomments', '{}: {}'.format(comm['from_id'], comm['text']))


    dm.wall.get(count=100, filter='others').walk(wall_cb)
    dm.sync()
