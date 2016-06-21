import time

def main(a, args):
    if not args:
        print('no uid')
        return
    uid = args[0]
    if uid[0] == 'c' and uid[1:].isdigit():
        uid = '2' + uid[1:].rjust(9, '0')
    else:
        try:
            uid = a.users.get(user_ids=uid)[0]['id']
        except Exception:
            print('fail')
            return
    while True:
        a.messages.setActivity(type='typing', user_id=uid)
        time.sleep(5)
