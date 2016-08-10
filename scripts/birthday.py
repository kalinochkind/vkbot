import datetime 
import config


def main(a, args):
    age = config.get('birthday.age', 'i')
    d = datetime.date.today()
    d = datetime.date(year=d.year-age, day=d.day, month=d.month)
    d += datetime.timedelta(days=1)
    print(d)
    a.account.saveProfileInfo(bdate=d.strftime('%d.%m.%Y'))

