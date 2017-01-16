import logging

import scriptlib

dist1 = {}
dist2 = {}
parent = {}

def main(a, args):
    a.ignored_errors = {
        (15, 'friends.get'): None,
        (18, 'friends.get'): None,
    }

    def getName(u):
        r = a.users.get(user_ids=u)[0]
        return r['first_name'] + ' ' + r['last_name']

    def addFriends(uid):
        dist = dist1 if uid in dist1 else dist2
        try:
            friends = a.friends.get(user_id=uid)['items']
        except TypeError:
            return
        logging.info('Scanning ' + str(uid))
        for i in friends:
            if i in parent:
                if i in dist:
                    continue
                chain1 = [uid]
                chain2 = [i]
                c = uid
                while c != start and c != end:
                    c = parent[c]
                    chain1.append(c)
                c = i
                while c != start and c != end:
                    c = parent[c]
                    chain2.append(c)
                chain = chain1[::-1] + chain2
                if chain[0] == end:
                    chain = chain[::-1]
                for uid in chain:
                    print('https://vk.com/id{} ({})'.format(uid, getName(uid)))
                exit()
            dist[i] = dist[uid] + 1
            parent[i] = uid

    start = scriptlib.resolvePid(a, args[0], False)
    end = scriptlib.resolvePid(a, args[1], False)
    if start is None or end is None:
        print('No such user')
        return
    if start == end:
        return
    print(start, end)
    dist1[start] = 0
    dist2[end] = 0
    parent[start] = -1
    parent[end] = -1
    addFriends(start)
    addFriends(end)
    for d in range(1, 10):
        for j in list(parent):
            if dist1.get(j) == d or dist2.get(j) == d:
                addFriends(j)
