from vkapi import vk_api
import check_friend
import config

def main(a, args):
    a.timeout = 10
    friends = []
    print('Fetching friends')
    for i in range(1000000):
        print('page', i)
        fr = a.friends.get(fields=check_friend.fields, count=1000, offset=i*1000)
        friends.extend(fr['items'])
        if len(fr['items']) < 1000:
            break

    print('Starting to delete')
    for i in friends:
        if not check_friend.is_good(i):
            a.friends.delete.delayed(user_id=i['id'])
            print('deleted', i['id'])
    a.sync()
    print()

    print('Fetching followers')
    foll = []
    for i in range(1000000):
        print('page', i)
        fr = a.users.getFollowers(fields=check_friend.fields, count=1000, offset=i*1000)
        foll.extend(fr['items'])
        if len(fr['items']) < 1000:
            break

    print('Starting to add')
    for i in foll:
        if check_friend.is_good(i):
            a.friends.add.delayed(user_id=i['id'])
            print('added', i['id'])
    a.sync()
    print()
    print('Finished')
