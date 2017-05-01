#include <regex>
#include <map>
#include "ChatBot.h"

inline bool isLetter(wchar_t c)
{
    if(L'a' <= c && c <= L'z')
        return 1;
    if(L'A' <= c && c <= L'Z')
        return 1;
    if(L'А' <= c && c <= L'я')
        return 1;
    return 0;
}

inline bool isDigit(wchar_t c)
{
    return (L'0' <= c && c <= L'9');
}

inline bool isVowel(wchar_t i)
{
    return i == L'а' || i == L'я' || i == L'о' || i == L'у' || i == L'ю' || i == L'и' || i == L'е';
}

void makeRussian(wstring &s)
{
    for(auto &i : s)
    {
        if(i == L'A') i = L'А';
        if(i == L'C') i = L'С';
        if(i == L'E') i = L'Е';
        if(i == L'K') i = L'К';
        if(i == L'M') i = L'М';
        if(i == L'O') i = L'О';
        if(i == L'P') i = L'Р';
        if(i == L'T') i = L'Т';
        if(i == L'X') i = L'Х';
        if(i == L'Y') i = L'У';
    }
}

long long phash(const wstring &s)
{
    auto word = s;
    makeRussian(word);
    long long ans = 0;
    for(auto i: word)
    {
        ans *= 1000000007LL;
        ans += i;
    }
    return ans;
}

long long phname = phash(L"firstname");

// <hash, <start, len> >
vector<pair<long long, pair<int, int> > > splitWords(const wstring &s, vector<pair<long long, long long> > &fixedstem, vector<pair<long long, long long> > &replaced, set<long long> &names)
{
    vector<pair<long long, pair<int, int> > > ans;
    wstring word;
    int prevKind = 0;  // 1 - letter, 2 - digit
    wstring S = s + L' ';
    for(int j=0;j<(int)S.size();j++)
    {
        wchar_t i = towupper(S[j]);
        if(isLetter(i) && prevKind != 2)
        {
            word.push_back(i);
            prevKind = 1;
        }
        else if(isDigit(i) && prevKind != 1)
        {
            word.push_back('0');
            prevKind = 2;
        }
        else
        {
            if(word.length())
            {
                bool st = 1;
                long long pw = phash(word);
                for(auto &t : fixedstem)
                {
                    if(t.first == pw)
                    {
                        pw = t.second;
//                        wcerr << pw << L" proc\n";
                        st = 0;
                        break;
                    }
                }
                if(names.count(pw))
                {
                    ans.push_back({phname, {j-word.length(), word.length()}});
                }
                else
                {
                    long long std = 0;
                    if(st)
                    {
                        std = stem(word);
                        for(auto &t : replaced)
                        {
                            if(std == t.first)
                            {
                                std = t.second;
                                break;
                            }
                        }
                    }
                    ans.push_back({st ? std : pw, {j-word.length(), word.length()}});
                }
            }
            word.clear();
            prevKind = 0;
            if(isLetter(i))
            {
                word.push_back(i);
                prevKind = 1;
            }
            else if(isDigit(i))
            {
                word.push_back('0');
                prevKind = 2;
            }
        }
    }
    return ans;
}

wregex PERFECTIVEGROUND(L"((ив|ивши|ившис)|(([ая])(в|вши|вшис)))$");

wregex REFLEXIVE(L"(ся)$");

wregex ADJECTIVE(L"(ие|ое|ими|ей|ий|ой|ем|им|ом|его|ого|ему|ому|их|ую|ая|ою|ею)$");

wregex PARTICIPLE(L"((ивш|уюш)|(([ая])(ем|вш|юш|ш)))$");

wregex VERB(L"((ила|ена|ейте|уйте|ите|или|ей|уй|ил|им|ен|ило|ено|ят|ует|уют|ени|ит|иш|ую)|(([ая])(ла|на|ете|йте|ли|й|л|ем|н|ло|но|ет|ют|ни|т|еш)))$");

wregex NOUN(L"(а|ев|ов|ие|е|иями|ями|ами|еи|и|ией|ей|ой|ий|й|иям|ям|ием|ем|ам|ом|о|у|ах|иях|ях|ию|ю|ия|я)$");

wregex DERIVATIONAL(L".*[^аеиоуюя]+[аеиоуюя].*ост$");

wregex DER(L"ост$");

wregex SUPERLATIVE(L"(ейше|ейш)$");

wregex I(L"и$");
map<long long, long long> stemmed;

wstring sstem(const wstring &wrd)
{
    int vp = -1;
    wstring word = L"";
    wchar_t p = 0;
    for(int _i=0;_i<(int)wrd.length();_i++)
    {
        wchar_t i = towlower(wrd[_i]);
        if(i == L'ь' || i == L'ъ')
            continue;
        if(i == L'ы')
            i = L'и';
        else if(i == L'э')
            i = L'е';
        else if(i == L'щ')
            i = L'ш';
        if(i == p && i != L'0')
            continue;
        p = i;
        word.push_back(i);
        if(vp < 0 && isVowel(i))
            vp = _i;
    }
    wsmatch m;
    if (vp >= 0)
    {
        wstring pre = word.substr(0, vp + 1);
        wstring rv = vp < (int)word.length() ? word.substr(vp + 1) : L"";
        wstring temp;
        temp = regex_replace(rv, PERFECTIVEGROUND, L"$4");
        if (temp == rv)
        {
            rv = regex_replace(temp, REFLEXIVE, L"");
            temp = regex_replace(rv, ADJECTIVE, L"");
            if (temp != rv)
            {
                rv = regex_replace(temp, PARTICIPLE, L"$4");
            }
            else
            {
                temp = regex_replace(rv, VERB, L"$4");
                if (temp == rv)
                {
                    rv = regex_replace(rv, NOUN, L"");
                }
                else
                {
                    rv = temp;
                }
            }
        }
        else
        {
            rv = temp;
        }
        rv = regex_replace(rv, I, L"");
        regex_match(rv, m, DERIVATIONAL);
        if (m.size())
        {
            rv = regex_replace(rv, DER, L"");
        }
        regex_replace(rv, SUPERLATIVE, L"");
        word = pre + rv;
    }
    return word;
}

long long stem(const wstring &wrd)
{

    long long h = phash(wrd);
    if(stemmed.count(h))
    {
        return stemmed[h];
    }
    return stemmed[h] = phash(sstem(wrd));
}


