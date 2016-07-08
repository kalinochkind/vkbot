import log
dist1 = {}
dist2 = {}
parent = {}

def resolveUid(a, uid):
    if uid.isdigit():
        return int(uid)
    if '/' in uid:
        uid = uid.split('/')[-1]
    return a.users.get(user_ids=uid)[0]['id']

def main(a, args):
    a.ignored_errors = {
        (15, 'friends.get'): None,
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
        log.info('Scanning ' + str(uid))
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
                for i in chain:
                    print('https://vk.com/id{} ({})'.format(i, getName(i)))
                exit()
            dist[i] = dist[uid] + 1
            parent[i] = uid

    start = resolveUid(a, args[0])
    end = resolveUid(a, args[1])
    if start == end:
        return
    dist1[start] = 0
    dist2[end] = 0
    parent[start] = -1
    parent[end] = -1
    addFriends(start)
    addFriends(end)
    for i in range(1, 10):
        for j in list(parent):
            if dist1.get(j) == i or dist2.get(j) == i:
                addFriends(j)
