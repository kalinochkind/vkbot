#!/usr/bin/python3

from vkapi import *
import check_friend
import datetime 
import config
import db_logger

login, password = config.get('login.login'), config.get('login.password')
age = config.get('birthday.age', 'i')
a = vk_api(login, password)
d = datetime.date.today()
d = datetime.date(year=d.year-age, day=d.day, month=d.month)
d += datetime.timedelta(days=1)
print(d)
a.account.saveProfileInfo(bdate=d.strftime('%d.%m.%Y'))
