import check_friend
import log
import accounts

def main(a, args):
    a.timeout = 10
    friends = []
    banned = list(map(int, open(accounts.getFile('banned.txt')).read().split()))
    log.info('Fetching friends')
    for i in range(1000000):
        log.info('page ' + str(i))
        fr = a.friends.get(fields=check_friend.fields, count=1000, offset=i*1000)
        friends.extend(fr['items'])
        if len(fr['items']) < 1000:
            break

    log.info('Starting to delete')
    for i in friends:
        if not (check_friend.isGood(i) or i['id'] in banned):
            a.friends.delete.delayed(user_id=i['id'])
            log.info('deleted ' + str(i['id']))

    log.info('\nFetching followers')
    foll = []
    for i in range(1000000):
        log.info('page ' + str(i))
        fr = a.users.getFollowers(fields=check_friend.fields, count=1000, offset=i*1000)
        foll.extend(fr['items'])
        if len(fr['items']) < 1000:
            break

    log.info('Starting to add')
    for i in foll:
        if check_friend.isGood(i):
            a.friends.add.delayed(user_id=i['id'])
            log.info('added ' + str(i['id']))
    log.info('\nFinished')
