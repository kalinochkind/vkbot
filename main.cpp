#include <clocale>
#include "ChatBot.h"
#include <unistd.h>

using namespace std;

int main()
{
    setlocale(LC_ALL, "");
    Load();
    char wd[256];
    getcwd(wd, sizeof(wd));
    wstring s;
    while(1)
    {
        wstring cmd;
        wcin >> cmd;
        if(cmd == L"reld")
        {
            Load();
            wcout << L"Reloaded!" << endl;
        }
        else if(cmd == L"user" || cmd == L"conf")
        {
            long long id;
            wcin >> id;
            getline(wcin, s, L'\n');
            wcout << Say(s, id, cmd == L"conf") << endl;
        }
        else if(cmd == L"flat")
        {
            getline(wcin, s, L'\n');
            wcout << Say(s, -1, 1) << endl;
        }
        else if(cmd.empty())
        {
            break;
        }
    }
    return 0;
}
