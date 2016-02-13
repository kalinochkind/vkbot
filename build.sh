#!/bin/sh

g++ main.cpp ChatBot.cpp Analyzer.cpp -O3 -march=atom -fno-exceptions -fno-stack-limit -W -Wshadow -Winline -Wdisabled-optimization -Wredundant-decls -Wunreachable-code -Wall -Wextra -Weffc++ -pedantic -pipe -fomit-frame-pointer -ffast-math -fno-rtti --std=c++11 -o chat.exe
chmod a+w chat.exe
