#ifndef __LOGGER_H
#define __LOGGER_H

#include <iostream>
#include <fstream>
#include <string>
#include <ctime>
#include <iomanip>

#include "utils.hpp"

class Logger {
public:
    Logger(const std::string& name, const std::string& path) : fileName(name), configPath(path)
    {
        std::ifstream infile(fileName);

        logFile_.open(fileName, std::ios::out);
        if (!logFile_.is_open()) {
            std::cerr << "Error: Failed to open the log file." << std::endl;
            exit(-1);
        }
    }

    ~Logger() {
        if (logFile_.is_open()) {
            logFile_.close();
        }
    }

    void log(const std::string& message)
    {
        logFile_ << message << std::endl;
    }

    void saveFile(const std::string& save)
    {
        std::ifstream src (this->configPath, std::ios::binary);
        std::ofstream dest (fileName + "-" + save, std::ios::binary);
        dest << src.rdbuf ();

        std::cout << "File copied successfully" << std::endl;
    }

private:
    std::ofstream logFile_;
    std::string configPath;
    std::string fileName;
};

#endif