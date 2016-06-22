#include <map>
#include <cmath>
#include <algorithm>
#include <fstream>
#include <ctime>
#include <memory>
#include "ChatBot.h"

struct userinfo
{
    unsigned smiles;
    int lastReply;
    long long context;
};

unsigned MAX_SMILES;

vector<wstring> request;
vector<shared_ptr<pair<vector<wstring>, long long> > > reply;
vector<pair<vector<long long>, long long> > tf;
vector<pair<long long, long long> > fixedstem;
vector<pair<long long, long long> > replaced;
vector<pair<long long, bool> > blacklist;
vector<long long> plain_blacklist;
vector<double> tfnorm;
map<long long, int> df;
map<int, userinfo> users;
set<long long> names;
map<long long, wstring> context_map;

inline double tfidf(long long &word)
{
    return df.count(word) ? log((double)tf.size() / df[word]) : 0.;
}

inline double sqr(double x)
{
    return x * x;
}

double norm(vector<long long> &arr)
{
    double ans = 0;
    for(auto&& i: arr)
    {
        ans += sqr(tfidf(i));
    }
    return sqrt(ans);
}

wstring RandReply(vector<wstring> &v)
{
    return v.size() == 1 ? v[0] : v[rand() % v.size()];
}

int randint(int a, int b)
{
    return rand() % (b - a + 1) + a;
}

void SwapFirst(vector<wstring> &v, bool canStay)
{
    if(v.size() > 1)
    {
        swap(v[0], v[randint(1 - canStay, v.size()-1)]);
    }
}

template<class T>
vector<long long> PlainWords(const vector<pair<long long, T> > &words_pos)
{
    vector<long long> words;
    for(auto &i : words_pos)
        words.push_back(i.first);
    return words;
}


void Highlight(wstring &line, const vector<pair<long long, pair<int, int> > > &words_pos, const vector<long long> &common)
{
    set<int> bpos;
    for(auto i : common)
    {
        for(auto& j : words_pos)
        {
            if(i == j.first)
            {
                bpos.insert(j.second.first);
                bpos.insert(-(j.second.first + j.second.second)-1);
            }
        }
    }
    int tadd = 0;
    for(int i=0;i<(int)line.size();i++)
    {
        if(bpos.count(-i-1))
        {
            line.insert(i+tadd, L"}`");
            tadd += 2;
        }
        if(bpos.count(i))
        {
            line.insert(i+tadd, L"`{");
            tadd += 2;
        }
    }
}

long long phnamec = phash(L"firstnamec");


//-1: comment
//-2: flat
wstring Say(wstring &line, int id, bool conf)
{
    line += L' ';
    long long context = users[id].context;
    if(line[1] == L'$' && id == -2)
    {
        wstring ctx;
        int i;
        for(i=2;line[i]!=L' ';i++)
        {
            ctx += line[i];
        }
        line = line.substr(i);
        context = phash(ctx);
    }
    auto words_pos = splitWords(line, fixedstem, replaced, names);
    vector<long long> words = PlainWords(words_pos);
    if(conf)
    {
        replace(words.begin(), words.end(), phname, phnamec);
    }
    sort(words.begin(), words.end());
    words.resize(unique(words.begin(), words.end()) - words.begin());
    for(auto &i : blacklist)
    {
        if(i.second && id != -1)
            continue;
        if(find(words.begin(), words.end(), i.first) != words.end())
        {
            Highlight(line, words_pos, (id==-1) ? PlainWords(blacklist) : plain_blacklist);
            wcerr << "red|" << line << L"- blacklisted\n";
            return L"$blacklisted";
        }
    }
    double mx = 0;
    int imx = 0;
    vector<long long> common;
    for(int i=0;i<(int)tf.size();i++)
    {
        if(tf[i].second != 0 && context != tf[i].second)
        {
            continue;
        }
        common.clear();
        set_intersection(words.begin(), words.end(), tf[i].first.begin(), tf[i].first.end(), back_inserter(common));
        double ans = 0;
        for(auto&& word: common)
        {
            ans += sqr(tfidf(word));
        }
        ans /= tfnorm[i];
        if(ans > mx + 0.00000001 || (tf[i].second && ans > mx - 0.00000001))
        {
            mx = ans;
            imx = i;
        }
    }
    if(mx == 0)
    {
        wcerr << "yellow|" << line << L"- no match\n";
        while(line.length() && line[0] == L' ')
        {
            line = line.substr(1);
        }
        if(id >= 0 && users[id].smiles >= MAX_SMILES)
        {
            if(!conf)
            {
                wcerr << "red|Too many smiles\n";
            }
            return L"";
        }
        if(id >= 0)
            users[id].smiles++;
        return L"$noans";
    }
    common.clear();
    set_intersection(words.begin(), words.end(), tf[imx].first.begin(), tf[imx].first.end(), back_inserter(common));
    Highlight(line, words_pos, common);
    wstring req = request[imx];
    Highlight(req, splitWords(req, fixedstem, replaced, names), common);
    wcerr << "green|" << line << L"== " << req << (tf[imx].second ? L" (context, " : L" (") << mx / norm(words) << L")";
    if(reply[imx]->first.size() > 1)
    {
        wcerr << L", " << reply[imx]->first.size() << L" replies";
    }
    wcerr << L"\n";
    if(id == -2)
    {
        for(int i=0;i<(int)reply[imx]->first.size();i++)
        {
            req += '|';
            req += reply[imx]->first[i];
        }
        req += '|';
        req += to_wstring(mx / norm(words));
        req += '|';
        req += context_map[reply[imx]->second];
        return req;
    }
    if(id >= 0)
    {
        users[id].context = reply[imx]->second;
        if(users[id].lastReply == imx + 1)
        {
            users[id].lastReply = -(imx + 1);
        }
        else if(users[id].lastReply == -(imx + 1))
        {
            wcerr << "red|Repeated\n";
            return L"";
        }
        else
        {
            users[id].lastReply = imx + 1;
        }
        users[id].smiles = 0;
    }
    wstring ans = reply[imx]->first[0];
    SwapFirst(reply[imx]->first, 0);
    return ans;
}

shared_ptr<pair<vector<wstring>, long long> > splitReply(const wstring &t)
{
    vector<wstring> ans;
    wstring s;
    wstring ctx;
    int i = 0;
    if(t[0] == L'$')
    {
        for(i=1;i<(int)t.size();i++)
        {
            if(t[i] == L' ')
            {
                i++;
                break;
            }
            ctx += t[i];
        }
    }
    for(;i<(int)t.size();i++)
    {
        if(t[i] == L'|')
        {
            if(s.length())
                ans.push_back(s);
            s.clear();
        }
        else
        {
            s.push_back(t[i]);
        }
    }
    if(s.length())
        ans.push_back(s);
    SwapFirst(ans, 1);
    context_map[phash(ctx)] = ctx;
    return make_shared<pair<vector<wstring>, long long> >(make_pair(ans, phash(ctx)));
}

void AddReply(const wstring &req, const wstring &rep)
{
    auto v = splitReply(rep);
    auto u = *splitReply(req);
    for(wstring& i : u.first)
    {
        reply.push_back(v);
        request.push_back(i);
        auto words_pos = splitWords(i, fixedstem, replaced, names);
        vector<long long> words = PlainWords(words_pos);
        sort(words.begin(), words.end());
        words.resize(unique(words.begin(), words.end()) - words.begin());
        for(auto& j: words)
        {
            df[j]++;
        }
        tf.push_back({words, u.second});
    }
}

wchar_t buf1[12000], buf2[12000];
const string file = "data/bot.txt";
const string filebl = "data/blacklist.txt";
const string filestem = "data/fixedstem.txt";
const string filenames = "data/names.txt";

void Load()
{
    locale loc("");
    reply.clear();
    request.clear();
    tf.clear();
    tfnorm.clear();
    df.clear();
    blacklist.clear();
    plain_blacklist.clear();
    fixedstem.clear();
    names.clear();
    context_map.clear();
    context_map[0] = L"";
    srand(time(0));
    wifstream fin(file);
    wifstream fstem(filestem);
    fstem.imbue(loc);
    while(fstem >> buf1)
    {
        fstem >> buf2;
        if(buf1[0] == '$')
        {
            replaced.push_back(make_pair(stem(buf1 + 1), stem(buf2)));
        }
        else
        {
            wstring s = buf1;
            for(auto &i : s)
                i = towupper(i);
            fixedstem.push_back(make_pair(phash(s), phash(buf2)));
        }
    }
    fstem.close();
    fin.imbue(loc);
    while(fin.getline(buf1, 10000))
    {
        fin.getline(buf2, 10000);
        AddReply(buf1, buf2);  //this should be done BEFORE filling names
    }
    df[phnamec] = 10000;
    for(auto&& i : tf)
    {
        tfnorm.push_back(norm(i.first));
    }
    fin.close();
    wifstream fbl(filebl);
    fbl.imbue(loc);
    while(fbl.getline(buf1, 10000))
    {
        if(buf1[0] == '$')
            blacklist.push_back({stem(buf1 + 1), 1});
        else
        {
            blacklist.push_back({stem(buf1), 0});
            plain_blacklist.push_back(stem(buf1));
        }
    }
    fbl.close();
    wifstream fnm(filenames);
    fnm.imbue(loc);
    while(fnm.getline(buf1, 10000))
    {
        for(int i=0;buf1[i];i++)
        {
            buf1[i] = towupper(buf1[i]);
        }
        names.insert(phash(buf1));
    }
    fbl.close();
    for(auto &i : users)
    {
        i.second.lastReply = 0;
    }
}

