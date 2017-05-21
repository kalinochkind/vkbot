import scriptlib

def main(a, args):
    if not args:
        print('Usage: ... -s dump filename')
        return
    with open(args[0], 'w') as f:
        dlg = scriptlib.getDialogs(a)
        print()
        for pid in dlg:
            if pid < 0:
                continue
            hist = scriptlib.getMessageHistory(a, pid)[::-1]
            cnt = 0
            for m1, m2 in zip(hist, hist[1:]):
                if m1.get('out') or not m2.get('out') or not m1.get('body') or not m2.get('body'):
                    continue
                f.write(m1['body'].replace('\n', ' ') + '\n' + m2['body'].replace('\n', ' ') + '\n')
                cnt += 1
            f.flush()
            print('Saved {} pairs\n'.format(cnt))
