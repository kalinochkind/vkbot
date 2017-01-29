#include <vector>
#include <string>
#include <iostream>
#include <set>

using namespace std;


wstring Say(wstring &curline, int id, bool conf);
void Load();
void LoadData(const wstring &data);
wstring Dump();

vector<pair<long long, pair<int, int> > > splitWords(const wstring &s, vector<pair<long long, long long> > &fixedstem, vector<pair<long long, long long> > &replace, set<long long> &names);
long long phash(const wstring &s);
long long stem(const wstring &word);
wstring sstem(const wstring &wrd);

extern int myName;
extern long long phname;
