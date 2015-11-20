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
    if(c == L'і' || c == L'І')
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

long long phash(const wstring &s)
{
    long long ans = 0;
    for(auto i: s)
    {
        ans *= 1000000007LL;
        ans += i;
    }
    return ans;
}

long long phname = phash(L"firstname");

vector<long long> splitWords(const wstring &s, vector<pair<long long, long long> > &fixedstem, vector<pair<long long, long long> > &replaced, set<long long> &names)
{
    vector<long long> ans;
    wstring word;
    for(auto i: s + L' ')
    {
        i = towupper(i);
        if(isLetter(i))
        {
            word.push_back(i);
        }
        else if(isDigit(i))
        {
            word.push_back('0');
        }
        else
        {
            if(word.length())
            {
                bool st = 1;
                long long pw = phash(word);
                for(auto &j : fixedstem)
                {
                    if(j.first == pw)
                    {
                        pw = j.second;
//                        wcerr << pw << L" proc\n";
                        st = 0;
                        break;
                    }
                }
                if(names.count(pw))
                {
                    ans.push_back(phname); 
                }
                else
                {
                    long long std = 0;
                    if(st)
                    {
                        std = stem(word);
                        for(auto &j : replaced)
                        {
                            if(std == j.first)
                            {
                                std = j.second;
                                break;
                            }
                        }
                    }
                    ans.push_back(st ? std : pw);
                }
            }
            word.clear();
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


long long stem(const wstring &wrd)
{
    //wcerr << word << L": ";
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
    long long h = phash(word);
    if(stemmed.count(h))
    {
        //wcerr << stemmed[word] << endl;
        return stemmed[h];
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
    return stemmed[h] = phash(word);
}


