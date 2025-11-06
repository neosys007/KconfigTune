#ifndef __COUNT_TIME_H
#define __COUNT_TIME_H

#include <iostream>
#include <fstream>
#include <chrono>
#include <cstdlib>
#include <unistd.h>
#include <thread>
#include <filesystem>

#include "log.hpp"

using namespace std::chrono;

int generateRandom(const int& len)
{
    srand(time(NULL));
    int randomNum = rand() % (len + 1);
    return randomNum;
}

enum NodeType
{
    Bool,
    Tristate,
    String,
    Int,
    Hex,
    And,
    Parent,
    Choice,
    Null
};

NodeType convertType(const std::string& type) {
    if (type.compare("bool") == 0) {
        return Bool;
    } else if (type.compare("tristate") == 0) {
        return Tristate;
    } else if (type.compare("int") == 0) {
        return Int;
    } else if (type.compare("hex") == 0) {
        return Hex;
    } else if (type.compare("string") == 0) {
        return String;
    }
    return Null;
}

std::vector<std::string> split(std::string str, const std::string& delimiter)
{
    std::vector<std::string> result;
    size_t pos = 0;
    while ((pos = str.find(delimiter)) != std::string::npos)
    {
        std::string token = str.substr(0, pos);
        result.push_back(token);
        str.erase(0, pos + delimiter.length());
    }
    result.push_back(str);
    return result;
}

void readConfigLine(std::string line, std::string &name, std::string &value)
{
    if (line.substr(0, 9) == "# CONFIG_")
    {
        name = std::regex_replace(line, std::regex("# CONFIG_"), "");
        name = std::regex_replace(name, std::regex(" is not set"), "");
        value = "not set";
    }
    else if (line.substr(0, 7) == "CONFIG_")
    {
        line = std::regex_replace(line.substr(7), std::regex("\n"), "");
        auto tmp = split(line, "=");
        name = tmp[0];
        if (tmp.size() > 2) {
            for (int i = 1; i < tmp.size(); ++i) {
                value += tmp[i];
            }
        } else {
            value = tmp[1];
        }
    }
}

bool checkFileExist(const std::string& path)
{
    std::ifstream infile(path);
    if (infile.good())
        return false;
    else
        return true;
}

bool checkFolderExistOrCreate(const std::string& path)
{
    if (!std::filesystem::exists(path)) {
        if (!std::filesystem::create_directory(path)) {
            std::cerr << "Failed to create directory: " << path << std::endl;
            exit(-1);
        } else {
            return true;
        }
    } else if (!std::filesystem::is_directory(path)) {
        std::cerr << "Path already exists but is not a directory: " << path << std::endl;
        exit(-1);
    } else {
        return true;
    }
}

void cpConfig(const std::string &source, const std::string &target)
{
    FILE *fp = NULL;
    std::string shell("cp " + source + " " + target);
    std::system(shell.c_str());
}

bool updateValue(const std::string &path, const NodeType type, const std::string& name, const std::string& value)
{
    if (chdir(path.c_str()) != 0) {
        std::cerr << "Failed to enter directory: " << path << std::endl;
        return false;
    }
    std::string command = "bash ./scripts/config";
    if (type == Bool || type == Tristate) {
        if (value.compare("y") == 0) {
            command += " -e " + name;
        } else {
            command += " -k -d " + name;
        }
        std::system(command.c_str());
        return true;
    } else if (type == Int || type == Hex) {
        command += " --set-val " + name + " " + value;
        std::system(command.c_str());
    } else if (type == String) {
        command += " --set-str " + name + " " + value;
        std::system(command.c_str());
    } else {
        std::cerr << "Unsupported type: " << type << std::endl;
        return false;
    }
    return false;
}

void compileLinuxKernel(int loopCount, Logger &logger)
{
    std::string kernelPath = "/home/guosy/Kconfig/OS/linux";
    std::string configPrev = ".config_prev";
    std::string configNext = ".config_next";

    chdir(kernelPath.c_str());

    system("make oldconfig");

    system(("cp .config " + configNext).c_str());

    for (int i = 1; i <= loopCount; ++i)
    {
        system("make clean");

        system(("cp " + configPrev + " .config").c_str());

        system(("make -j" + std::to_string(std::thread::hardware_concurrency()) + " bzImage modules").c_str());

        system(("cp " + configNext + " .config").c_str());

        auto start = std::chrono::high_resolution_clock::now();
        system(("make -j" + std::to_string(std::thread::hardware_concurrency()) + " bzImage modules").c_str());
        auto end = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
        std::cout << "第 " << i << " 次Linux内核的编译时间为 " << duration << " 毫秒" << std::endl;

        logger.log("第 " + std::to_string(i) + " 次Linux内核的编译时间为 " + std::to_string(duration) + " 毫秒");
    }
}

void detectUnmetDepend()
{
    
}

#endif