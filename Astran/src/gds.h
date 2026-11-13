/*
 * gds.h
 * veja gds.cpp
 * Bernardo Honaiser - bphonaiser@inf.ufrgs.br
 */

#pragma once

#include <fstream>
#include <string>
#include <vector>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "util.h"

class Gds {
public:
    Gds(string);
    ~Gds();
    bool open();
    void generateHeader(int);
    void generateUnits();
    void generateLibrary();
    void generateLibname(char*);
    void generateStruct();
    void generateStructname(char*);
    void generateString(const char* a);
    // Rectangle as a closed BOUNDARY element on layer/datatype (database units).
    void generateBoundary(int layer, int datatype, long x1, long y1, long x2, long y2);
    // TEXT element on layer/texttype at (x, y) (database units).
    void generateText(int layer, int texttype, long x, long y, const char* text);
    void generateEndelement();
    void generateEndStruct();
    void generateEndLibrary();
    void add_longint(long int&);
    void add_int16(int v);
    void add_int32(long v);

private:
    union conv_2b{
        char c[2];
        int l;
    };


    union conv_4b{
        char c[4];
        long int l;
    };

   ofstream file;
   string filename;
   vector<char> f;
   time_t tempo;
   tm ts;
   long int x1, x2, y1, y2;
   short int layer;
   void write();
};
