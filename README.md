# vkbot
Chat-bot for vk.com

Does not work on Windows. Tested with Python 3.5. gcc >= 4.9 required. The database is located at the `data` directory.

Run: inf.py [-l] [-d] [-a account]

-l: write all VK api requests to inf.log, 
-d: logging to MySQL (`mysql.connector` required)

Needs `antigate` package to support captcha recognition using anti-captcha.com. 
