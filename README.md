# vkbot
Chat-bot for vk.com

Does not work on Windows. Tested with Python 3.5. gcc >= 4.9 required. The database is located at the `data` directory.

Run: `inf.py [-l] [-d] [-a account] [-w whitelist] [-s script script_args]`

`-l`: write all VK api requests to inf.log

`-d`: logging to MySQL (`mysqlclient` required)

`-w`: reply only to users from the white list (comma-separated list of ids, domains or full names)

`-s`: run a script from `scripts` directory

Needs `antigate` package to support captcha recognition using anti-captcha.com. 
