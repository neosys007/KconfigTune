#include <cstdio>
#include <fstream>
#include <iostream>
#include <vector>
#include <unordered_map>
#include <regex>
#include <algorithm>

#include "nlohmann/json.hpp"
#include "Tree.hpp"
#include "parse.hpp"
#include "utils.hpp"
#include "log.hpp"

using json = nlohmann::json;
using namespace std;

/* 
 * root:  在几个节点下改
 * count: 改几个节点
 * root <= count
 * path : linux 内核地址
 */
void changeNode(TreeForest &forest, int root, int count, string path, Logger &logger)
{
    // cpConfig(path+"/.config", path+"/.config_prev");
    // logger.saveFile("origin");

    int index = generateRandom(forest.getRootsLen() - 1);
    logger.log("target root index => " + to_string(index));

    if (root == 1)
    {
        for (int i = 0; i < count; ++i)
        {
            int res = forest.changeOneNode(index, logger);
            if (res == 0) {
                ++ index;
                --i;
            } else {
                i += res;
            }
        }
    }
    else
    {
        for (int i = index, nums = count / root; i < root + index; ++i) {
            for (int j = 0; j < nums; ++j) {
                int res = forest.changeOneNode(i, logger);
                if (res == 0) {
                    ++i;
                    ++root;
                    ++nums;
                } else {
                    j += res;
                }
            }
        }
    }
    forest.change2config(path);
    // cpConfig(path+"/.config", path+"/.config_next");
    logger.saveFile("modify");
}

void countCompilerTime(const string& linux_path, \
                        TreeForest &forest, \
                        const string& log_path)
{
    int root = 5;
    int count = 100;
    int average = 1;

    std::time_t now = std::time(nullptr);
    std::tm* local_time = std::localtime(&now);
    char buf[80];
    std::strftime(buf, sizeof(buf), "%Y-%m-%d-%H:%M:%S", local_time);

    string folder = log_path + "/" + std::to_string(root) + "-" + \
                    std::to_string(count) + "-" + std::to_string(average) + "_" + string(buf);

    checkFolderExistOrCreate(folder);
    string file = folder + "/" + to_string(root) + "-" + to_string(count) + "-" + to_string(average);
    Logger logger(file, linux_path + "/.config");

    logger.saveFile("origin");

    changeNode(forest, root, count, linux_path, logger);
    forest.printChange(logger);

    // string bash_path = "/home/guosy/Kconfig/source/count_time/time.sh";

    // system((bash_path + " " + to_string(average)).c_str());
    compileLinuxKernel(average, logger);

    logger.saveFile("comipler");
}

void ChangeNode(const string& linux_path, TreeForest &forest, const string& log_path)
{
    string name = "SND_USB_6FIRE";
    vector<string> list;
    list.emplace_back(name);
    forest.changeVecNode(list);

    // Logger logger(result, linux_path + "/.config");

    cpConfig(linux_path+"/.config", linux_path+"/.config_prev");
    forest.change2config(linux_path);
    cpConfig(linux_path+"/.config", linux_path+"/.config_next");

    // forest.printChange(logger);

    string command = "cd " + linux_path;
    system(command.c_str());
    command = "make -j $(nproc) bzImage modules";
    system(command.c_str());
}

int main(int argc, char const *argv[])
{
    // Linux内核地址
    string linux_path = "/home/guosy/Kconfig/OS/linux";
    // log保存地址
    string log_dir_path = "/home/guosy/Kconfig/source/count_time/Log";
    TreeForest forest("/home/guosy/Kconfig/source/count_time/forest.bin");
    // json文件地址
    string config_json("/home/guosy/Kconfig/v6.2-x86/v6.2_x86_config.json");

    forest.updateArchConfig(config_json);
    parser(config_json, &forest);
    forest.updateNodeValue(linux_path + "/.config");

    // forest.printArchNodes();
    // forest.printAllNodes();
    // forest.printRoots();

    countCompilerTime(linux_path, forest, log_dir_path);
    // testChangeNode(linux_path, forest);

    return 0;
}