import random
import mimetypes
import urllib.request
import json

def uploadFile(url, path, post_field):
    boundary = '-----------------' + str(random.randint(1, 1000000000000000000))
    parts = []
    parts.append('--' + boundary)
    parts.append('Content-Disposition: form-data; name="{}"; filename="file.jpg"'.format(post_field))
    parts.append('Content-Type: ' + (mimetypes.guess_type(path)[0] or 'application/octet-stream'))
    parts.append('')
    parts.append(open(path, 'rb').read())

    parts.append('--' + boundary + '--')
    parts.append('')

    body = b'\r\n'.join(i.encode() if isinstance(i, str) else i for i in parts)
    headers = {'content-type': 'multipart/form-data; boundary=' + boundary}
    req = urllib.request.Request(url, headers=headers, data=body)
    res = urllib.request.urlopen(req)

    return json.loads(res.read().decode())
