#include <clocale>
#include <cstring>
#include <csignal>
#include "ChatBot.h"

using namespace std;

extern unsigned MAX_SMILES;
extern int myName;

int main(int argc, char* argv[])
{
    signal(SIGINT, SIG_IGN);
    setlocale(LC_ALL, "C.UTF-8");
    if(argc >= 3)
    {
        MAX_SMILES = atoi(argv[1]);
        myName = atoi(argv[2]);
    }
    else
    {
        MAX_SMILES = -1;
        myName = -1;
    }
    Load();
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
        else if(cmd == L"comm")
        {
            getline(wcin, s, L'\n');
            wcout << Say(s, -1, 0) << endl;
        }
        else if(cmd == L"flat")
        {
            int conf;
            wcin >> conf;
            getline(wcin, s, L'\n');
            wcout << Say(s, -2, conf) << endl;
        }
        else if(cmd == L"stem")
        {
            getline(wcin, s, L'\n');
            wcout << sstem(s) << endl;
        }
        else if(cmd == L"dump")
        {
            wcout << Dump() << endl;
        }
        else if(cmd == L"load")
        {
            getline(wcin, s, L'\n');
            LoadData(s);
            wcout << L"Loaded!" << endl;
        }
        else if(cmd.empty())
        {
            break;
        }
    }
    return 0;
}
