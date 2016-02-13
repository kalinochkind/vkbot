#include <vector>
#include <string>
#include <iostream>
#include <set>

using namespace std;

#define MAX_SMILES 1

wstring Say(wstring &curline, int id, bool conf);
void Load();

vector<long long> splitWords(const wstring &s, vector<pair<long long, long long> > &fixedstem, vector<pair<long long, long long> > &replace, set<long long> &names);
long long phash(const wstring &s);
long long stem(const wstring &word);

extern long long phname;
