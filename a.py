#!/usr/bin/python3

from vkapi import *
import check_friend

login, password = open('data.txt').read().split()[:2]
a = vk_api(login, password, 10)
a.delayedReset()
friends = []
print('Fetching friends')
noadd = check_friend.noadd
for i in range(1000000):
    print('page', i)
    fr = a.friends.get(fields=check_friend.fields+',can_write_private_message', count=1000, offset=i*1000)
    friends.extend(fr['items'])
    if len(fr['items']) < 1000:
        break

print('Starting to delete')
for i in friends:
    if not i['can_write_private_message']:
        noadd.add(str(i['id']))
    if not check_friend.is_good(i):
        a.friends.delete.delayed(user_id=i['id'])
        print('deleted', i['id'])
a.sync()
print()

with open('noadd.txt', 'w') as f:
    f.write('\n'.join(noadd))

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
