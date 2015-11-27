#!/usr/bin/python3

from vkapi import *
import check_friend
import datetime 

login, password = open('data.txt').read().split()[:2]
a = vk_api(login, password, 10)
d = datetime.date.today()
d = datetime.date(year=d.year-15, day=d.day, month=d.month)
d += datetime.timedelta(days=1)
print(d)
a.account.saveProfileInfo(bdate=d.strftime('%d.%m.%Y'))
