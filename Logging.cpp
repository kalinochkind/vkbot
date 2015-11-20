// not used

#include "ChatBot.h"
#include <fstream>
#include <ctime>

const string log_filename = "chat.log";
wofstream log;

void initLogging()
{
    log.close();
    log.open(log_filename, ofstream::out | ofstream::app);
    log.imbue(locale(""));
}

void logWrite(wstring s)
{
    time_t cur;
    time(&cur);
    struct tm * timeinfo = localtime(&cur);
    char buffer[80];
    strftime(buffer, 80, "%m:%d:%y %X", timeinfo);
    log << '[' <<  buffer << "] " << s << endl;
    log.flush();
}