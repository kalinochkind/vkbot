#include <clocale>
#include "ChatBot.h"

using namespace std;

extern unsigned MAX_SMILES;

int main(int argc, char* argv[])
{
    setlocale(LC_ALL, "ru_RU.UTF-8");
    Load();
    if(argc == 1)
        MAX_SMILES = (unsigned) -1;
    else
    {
        MAX_SMILES = atoi(argv[1]);
    }
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
        else if(cmd.empty())
        {
            break;
        }
    }
    return 0;
}
