import csv
import scriptlib

def main(a, args):
    if not args:
        print('Usage: ... -s dump filename')
        return
    with open(args[0], 'w') as f:
        writer = csv.writer(f, delimiter='\t')
        dlg = scriptlib.getDialogs(a)
        print()
        for i, pid in enumerate(dlg):
            print('{}/{}'.format(i + 1, len(dlg)))
            if pid < 0:
                continue
            hist = scriptlib.getMessageHistory(a, pid)[::-1]
            cnt = 0
            for m in hist:
                writer.writerow([m['id'], m['date'], m['peer_id'], m['from_id'], m.get('reply_message', {}).get('id', ''), m.get('text', '')])
            f.flush()
            print()
