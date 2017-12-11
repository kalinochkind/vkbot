# -*- coding: utf-8 -*-
import re

rep = {
    "ноль": "0", "нуль": '0', "один": "1", "два": "2", "дважды": "2*", "три": "3", "трижды": "3*", "четыре": "4", "четырежды": "4*", "пять": "5",
    "пятью": "5*",
    "шесть": "6", "шестью": "6*", "семь": "7", "семью": "7*", "восемь": "8", "восемью": "8*", "девять": "9", "девятью": "9*",
    "десять": "10", "одиннадцать": "11", "одинадцать": "11", "двенацать": "12", "тринадцать": "13", "четырнадцать": "14", "пятнадцать": "15",
    "шестнадцать": "16", "семнадцать": "17", "восемнадцать": "18", "девятнадцать": "19",
    "двадцать": "20", "тридцать": "30", "сорок": "40", "пятьдесят": "50",
    "шестьдесят": "60", "семьдесят": "70", "восемьдесят": "80", "восемдесят": "80", "девяносто": "90", "девяноста": "90"
}
op = {"плюс": "+", "минус": "-", "прибавить": "+", "отнять": "-", "умножить": "*", "разделить": "//", "делить": "//"}
allowed = set('йцукенгшщзхъфывапролджэячсмитьбю.1234567890()+-*/ ')
not_a_minus = re.compile(r'(?<=[a-zа-я])-(?=[a-zа-я])', re.IGNORECASE)
seq_minus = re.compile(r'([^\d\-\*\+]+\d+(-\d+)+)|(\d+(-\d+)+[^\d\-\*\+=]+)')

def isnum(s):
    return s and (s.isdigit() or s[0] == '-' and len(s) > 1 and s[1:].isdigit())

def evalExpression(s):
    s = s.replace('\u00d7', '*').replace('\u2022', '*').replace('\u00f7', '/')
    if seq_minus.match(s):
        return None
    s = not_a_minus.sub(' ', s)
    s = s.replace('(', ' ( ').replace(')', ' ) ').replace('+', ' + ').replace('-', ' - ').replace('*', ' * ').replace('/', ' // ')
    if '[' in s:
        return None
    s = ''.join(i if i in allowed else ' ' for i in s.lower()).split()
    ans = []
    for i in s:
        if set(i) <= set('0123456789+-*/() '):
            ans.append(i)
        elif i in op:
            ans.append(op[i])
        elif i in rep:
            ans.append(rep[i])
    for i in range(1, len(ans)):
        if ans[i].isdigit() and ans[i - 1].isdigit():
            a = int(ans[i])
            b = int(ans[i - 1])
            if 1 <= a <= 9 and 20 <= b <= 90 and b % 10 == 0:
                ans[i] = str(int(ans[i]) + int(ans[i - 1]))
                ans[i - 1] = ''
            else:
                return None
    s = ''.join(ans).strip()
    if not s:
        return None
    if s[0] == '+' or isnum(s) or isnum(s.replace('(', '').replace(')', '').strip('+').strip('-')):
        return None
    if '**' in s or '--' in s or '++' in s or '-0' in s:
        return None
    if set(s) <= set('0123456789()-') and s[0] == '8':
        return None
    try:
        res = str(eval(s, {'__builtins__': {}}))
    except ZeroDivisionError:
        return None
    except Exception:
        s = s.replace('(', ' ').replace(')', ' ').strip()
        if not s or s[0] == '+' or isnum(s) or isnum(s.strip('+')):
            return None
        if '**' in s or '--' in s or '++' in s or '-0' in s or ''.join(s.split()) == '1*1':
            return None
        try:
            res = str(eval(s, {'__builtins__': {}}))
        except Exception:
            return None
    s = s.lstrip('-')
    if set(s) <= set('0123456789-') and s.count('-') == 1 and int(res) <= 0:
        return None
    if s == '24//7':
        return None
    ss = s.split('//')
    if len(ss) == 2 and ss[0] == ss[1]:
        return None
    if isnum(res) and res != '0' and len(res) < 80:
        return res
    else:
        return None

if __name__ == "__main__":
    while True:
        line = input()
        print(evalExpression(line))
