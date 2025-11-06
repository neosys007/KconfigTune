#ifndef __TREE_H
#define __TREE_H

#include <cstdio>
#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include <fstream>
#include <unordered_map>
#include <deque>
#include <regex>
#include <stack>

#include "nlohmann/json.hpp"
#include "utils.hpp"
#include "log.hpp"

using json = nlohmann::json;

typedef struct {
    std::string value;
    std::string if_condition;
} unionIF;

class TreeNode
{
    // op 和 if_condition 合为一个vector
    std::string op;
    std::string if_condition;
    std::vector<unionIF> Default;
    std::vector<unionIF> Range;
    std::vector<unionIF> Select;

public:
    std::string name;
    std::string value;
    NodeType type;

    std::vector<TreeNode *> children;
    std::vector<TreeNode *> father;
    std::vector<TreeNode *> allChild;

    TreeNode(NodeType type) : type(type) {
        name = "NULL";
        value = "not set";
    }

    TreeNode(std::string v, NodeType type) : name(v), type(type) {
        value = "not set";
    }

    TreeNode(std::string v, TreeNode *kid, NodeType type) : name(v), type(type)
    {
        children.emplace_back(kid);
        value = "not set";
    }

    // json load()
    // {
    //     json save;
    //     save["op"] = 
    // }

    void updateDefault(const unionIF& data) {
        Default.emplace_back(data);
    }

    /* flag = true ,开启配置项
     * flag = false, 关闭配置项
     */
    std::string getDefault(std::unordered_map<std::string, TreeNode *> *save, bool flag) {
        // 如果有if，查看if是否成立
        // 返回一个符合的节点
        for (auto item : this->Default) {
            if (item.if_condition.size()) {
                auto tmp = save->find(item.if_condition);
                if (tmp != save->end()) {
                    TreeNode* node = tmp->second;
                    if (node->value.compare("not set") != 0 || node->value.compare("n") != 0)
                        return item.value;
                }
            }
            else if (item.value.size() || this->type == String) 
            {
                if (this->type == String && item.value.size() == 0)
                    return "\"\"";
                return item.value;
            }
        }
        // 如果没有default
        // 看是不是int、hex，如果是有range
        // 如果是bool或tristate
        if (this->type == Int || this->type == Hex) {
            for (auto item : this->Range) {
                auto tmp = save->find(item.if_condition);
                if (tmp != save->end()) {
                    TreeNode* node = tmp->second;
                    if (node->value.compare("not set") != 0 || node->value.compare("n") != 0) {
                        auto res = split(item.value, " ");
                        return res[0];
                    }
                }
            }
        } else if (this->type == Bool || this->type == Tristate) {
            if (flag) return "y";
            else return "n";
        } else if (this->type == String) {
            return "";
        }
        exit(-1);
    }

    // std::string getRange() {
    //     for (auto item : Range) {
    //         return item.value;
    //     }
    // }

    void updateRange(const unionIF& data) {
        Range.emplace_back(data);
    }

    void updateSelect(const unionIF& data) {
        Select.emplace_back(data);
    }

    void updateType(NodeType type)
    {
        this->type = type;
    }

    void addChildren(TreeNode *save)
    {
        if (std::count(children.begin(), children.end(), save) == 0)
            this->children.emplace_back(save);
    }

    void addKid(TreeNode *save)
    {
        if (save != nullptr)
            if (std::count(allChild.begin(), allChild.end(), save) == 0)
                this->allChild.emplace_back(save);
    }

    void addFather(TreeNode *save)
    {
        if (std::count(father.begin(), father.end(), save) == 0)
            this->father.emplace_back(save);
    }

    void updateInfo(std::string op, std::string con)
    {
        this->op = op;
        this->if_condition = con;
    }

    std::vector<TreeNode *>getKid()
    {
        return this->children;
    }

    std::vector<TreeNode *> getFather()
    {
        return this->father;
    }
};

class TreeForest
{
    std::string tmpFile;
    std::vector<TreeNode *> roots;
    std::unordered_map<std::string, TreeNode *> save;
    std::vector<std::string> ArchNodes;
    std::unordered_map<std::string, std::string> change;

    std::unordered_map<std::string, TreeNode *> choice;

    template<typename T>
    bool hasNode(std::vector<T> list, T target)
    {
        if (std::find(list.begin(), list.end(), target) != list.end())
            return true;
        else
            return false;
    }
    // 暂时没用
    TreeNode* findNode(std::string name)
    {
        std::deque<TreeNode *> list;
        for (auto root : roots)
        {
            if (root->name.compare(name) == 0)
                return root;
            list.emplace_back(root);
        }
        for (TreeNode *target = list[0]; list.size(); target = list[0])
        {
            list.pop_front();
            for (auto item : target->getKid())
            {
                if (item->name.compare(name) == 0)
                    return item;
                list.emplace_back(item);
            }
        }
        return nullptr;
    }
    
    //暂时没用
    int countNodes(TreeNode *node, std::vector<std::string>& haveFind)
    {
        if (!node)
        {
            return 0;
        }
        if (node->name.compare("AND") != 0 && std::count(haveFind.begin(), haveFind.end(), node->name) == 0)
            haveFind.emplace_back(node->name);
        int count = 1;
        for (TreeNode *child : node->getKid())
        {
            count += countNodes(child, haveFind);
        }

        return count;
    }

    std::vector<TreeNode *> stk2vec(std::stack<TreeNode*> *stk) {
        std::vector<TreeNode *> vec;
        while (stk->size()) {
            vec.emplace_back(stk->top());
            stk->pop();
        }
        return vec;
    }

    void travseseAndParent(TreeNode* node, std::stack<TreeNode*> *stk) {
        if (node->type != And && node -> type != Parent) {
            stk->push(node);
        } else {
            for (auto &tmp : node -> children) {
                travseseAndParent(tmp, stk);
            }
        }
    }

    void traverseFather(TreeNode* node, std::vector<std::vector<TreeNode*>> *list, std::stack<TreeNode*> *stk)
    {
        for (auto &node : node -> father) {
            if (node->type == And || node -> type == Parent) {
                int size_save = stk->size();
                for (auto &tmp : node -> children) {
                    if (node->type == And || node -> type == Parent) {
                        travseseAndParent(node, stk);
                    } else {
                        stk->push(tmp);
                    }
                }
                for (auto &tmp : node -> children) {
                    traverseFather(node, list, stk);
                }
                while (stk->size() > size_save) {
                    stk->pop();
                }
            } else {
                stk->push(node);
                if (node->father.size() == 0) {
                    list->emplace_back(stk2vec(stk));
                } else {
                    traverseFather(node, list, stk);
                }
                stk->pop();
            }
        }
    }
    
    // 暂时没用
    void traverseSaveNodesAndWriteToChange()
    {
        for (const auto& pair : save)
        {
            const std::string& key = pair.first;
            TreeNode* node = pair.second;
            std::string value = "not set";
            if ((node->type == Bool || node->type == Tristate) &&  node->value == value)
                change[key] = value;
        }
    }

    int closeChildren(std::string name)
    {
        auto tmp = save.find(name);
        int result = 0;
        if (tmp != save.end()) {
            TreeNode* target = tmp->second;
            for (const auto& item : target -> allChild)
            {
                if (item->value.compare("not set") == 0) {
                    // int、hex、string如果不想设置通常依赖会不成立
                    // 否则会指定默认值或range等其他形式
                    if (item->type == Int || item->type == Hex) {
                        std::string res = item->getDefault(&(this->save), false);
                        this->change[item->name] = res;
                        ++result;
                        result += closeChildren(item->name);
                    } else if (item->type == String) {
                        std::string res = item->getDefault(&(this->save), false);
                        this->change[item->name] = res;
                        ++result;
                        result += closeChildren(item->name);
                    } else if (item->type == Bool || item->type == Tristate) {
                        this->change[item->name] = "not set";
                    }
                }
            }
        }
        return result;
    }

    int openFather(std::string name)
    {
        auto tmp = save.find(name);
        int result = 0;
        if (tmp != save.end()) {
            TreeNode* target = tmp->second;
            for (const auto& item : target -> allChild)
            {
                if (item->value.compare("not set") == 0) {
                    if (item->type == Bool || item->type == Tristate) {
                        std::vector<std::vector<TreeNode *>> list;
                        std::stack<TreeNode *> stk;
                        traverseFather(item, &list, &stk);
                        // list中选择一个vector数量最小的
                        if (list.size()) {
                            std::vector<TreeNode*> res = list[0];
                            for (int i = 1; i < list.size(); ++i) {
                                if (list[i].size() < res.size()) {
                                    res = list[i];
                                }
                            }
                            for (int i = 0; i < res.size(); ++i) {
                                change[res[i]->name] = res[i]->getDefault(&(this->save), true);
                            }
                        }
                    } else if (item->type == Int || item->type == Hex) {
                        std::string res = item->getDefault(&(this->save), true);
                        this->change[item->name] = res;
                        ++result;
                        result += closeChildren(item->name);
                    } else if (item->type == String) {
                        std::string res = item->getDefault(&(this->save),true);
                        this->change[item->name] = res;
                        ++result;
                        result += closeChildren(item->name);
                    }
                }
            }
        }
        return result;
    }

public:
    TreeForest(std::string path) : tmpFile(path){}

    void load()
    {
        if (checkFileExist(this->tmpFile)) {
            std::cout << "file not exist" << std::endl;
            exit(-1);
        }
    }

    void read()
    {
        // json save;
        // json roots;
        // for (int i = 0; i < this->roots.size(); ++i)
        // {
        //     roots[std::to_string(i)] = 
        // }

        // save["roots"] = roots;


    }

    void changeVecNode(const std::vector<std::string> &vec)
    {
        for (auto name : vec) {
            change[name] = "y";
            closeChildren(name);
            openFather(name);
        }
    }

    TreeNode* updateChoice(const std::string &name, TreeNode *Kid)
    {
        auto tmp = save.find(name);
        TreeNode* target;
        if (tmp == save.end()) {
            target = new TreeNode(name, Choice);
        } else {
            target->addChildren(Kid);
        }
        choice[name] = target;
        return target;
    }

    void updateDetail(const std::string &name, std::string data, std::string if_condition, const std::string &flag)
    {
        auto target = save[name];
        unionIF tmp;
        if (flag.compare("default") == 0)
        {
            data = regex_replace(data, std::regex(" "), "");
            data = regex_replace(data, std::regex("\""), "");
        }
        else if (flag.compare("range") == 0)
        {
            data = data.substr(1, data.size() - 1);
        }
        else if (flag.compare("select") == 0)
        {
            // 一般不用处理
        }
        if_condition = regex_replace(if_condition, std::regex(" "), "");
        if_condition = regex_replace(if_condition, std::regex("\""), "");
        tmp.value = data;
        tmp.if_condition = if_condition;
        if (flag.compare("default") == 0)
            target->updateDefault(tmp);
        else if (flag.compare("range") == 0)
            target->updateRange(tmp);
        else if (flag.compare("select") == 0)
            target->updateSelect(tmp);
    }

    int getRootsLen() {
        return this->roots.size();
    }
    /* target: 标记需要修改的哪个root点
     * 在这个root点下增加一个Node的配置
     */
    int changeOneNode(int target, Logger& logger)
    {
        TreeNode* prev = nullptr;
        // bool flag = true;
        int flag = 0;
        while (flag == 0) {
            prev = roots[target];
            switch (prev->type)
            {
                case Bool : case Tristate:
                {
                    if (prev->value.compare("n") == 0 || prev->value.compare("not set") == 0) {
                        this->change[prev->name] = "y";
                        prev->value = "y";
                        ++ flag;
                        flag += closeChildren(prev->name);
                        return flag;
                    } else flag = -1;
                    break;
                }
                case Int : case Hex:
                {
                    if (prev->value.compare("not set") != 0) {
                        // logger.log(prev->name + "\t:\t" + prev->type);
                    } else flag = -1;
                    break;
                }
                case String:
                {
                    if (prev->value.compare("not set") != 0) {
                        // logger.log(prev->name + "\t:\t" + prev->type);
                    } else flag = -1;
                    break;
                }
                case And: case Parent:
                {
                    exit(-1);
                }
                default:
                    exit(-1);
            }
            ++target;
        }
        std::cout << prev->name << std::endl;
        flag = (flag == -1) ? 0 : flag;
        for (TreeNode* tmp : prev->getKid()) {
            switch (tmp->type)
            {
                case Bool : case Tristate:
                {
                    if (tmp->value.compare("n") == 0 || tmp->value.compare("not set") == 0) {
                        this->change[tmp->name] = "y";
                        tmp->value = "y";
                        flag += closeChildren(tmp->name);
                        return flag;
                    }
                }
                case Int : case Hex:
                {
                    break;
                }
                case String:
                {
                    break;
                }
                case And:
                {
                    // 查看父节点是不是都成立，如果是，把子节点选中，返回
                    break;
                }
                case Parent:
                {
                    // 内部选值
                    break;
                }
            }
        }
        return flag;
    }

    bool changeNode(std::string name, std::string value) {
        auto tmp = save.find(name);
        if (tmp == save.end()) {
            return false;
        }
        TreeNode *node = tmp->second;
        // 检查value是否合规
        // change存信息
        change[name] = value;
        closeChildren(node->name);
        openFather(node->name);
    }

    void printChange(Logger &logger)
    {
        // printf("\n\nprint change => **********************\n");
        logger.log("print change =>");
        for(auto &item : change)
        {
            // if (item.second.compare("not set") != 0) {
                // std::cout << "\t" + item.first + " : " + item.second << std::endl;
                logger.log("\t" + item.first + " : " + item.second);
            // }
        }
    }

    void change2config(const std::string &path)
    {
        for (auto it = change.begin(); it != change.end(); ++it)
        {
            std::string name = it -> first;
            std::string value = it -> second;
            auto iter = save.find(name);
            updateValue(path, iter->second->type, name, value);
        }
    }

    void updateArchConfig(const std::string &path)
    {
        std::ifstream test(path);
        json data = json::parse(test);

        for (auto item : data.items())
        {
            ArchNodes.emplace_back(item.key());
        }
    }

    void updateNodeValue(const std::string &path)
    {
        std::ifstream test(path);
        std::string line;
        while (getline(test, line))
        {
            std::string name;
            std::string value;
            readConfigLine(line, name, value);
            auto target = save.find(name);
            if (target != save.end())
            {
                TreeNode* node = save[name];
                node->value = value;
            }
        }
    }

    std::vector<std::string> getArchNode() {
        return ArchNodes;
    }

    void printNode(TreeNode* node)
    {
        std::cout << node->name + "(value = " + node->value + ")\tchildren : ";
        for (auto kid : node->getKid())
        {
            // 如果是AND，打印AND的子节点
            std::cout << kid->name + "\t";
        }
        std::cout << std::endl;
}

    void printRoots()
    {
        int index = 0;
        for (auto root : roots)
        {
            std::cout << index++ << "\t:\t";
            printNode(root);
        }
    }

    void printAllNodes()
    {
        for(auto it = save.begin(); it != save.end(); ++it) {
            printNode(it->second);
        }
    }

    void printArchNodes()
    {
        for (int i = 0; i < ArchNodes.size(); ++i)
        {
            std::cout << ArchNodes[i] << std::endl;
        }
    }

    TreeNode* addNode(std::string name, NodeType type)
    {
        if (hasNode(this->ArchNodes, name))
        {
            auto flag = save.find(name);
            if (flag != save.end())
            {
                if (type != Null)
                    save[name]->updateType(type);
                return save[name];
            }
            TreeNode *target = new TreeNode(name, type);
            this->roots.emplace_back(target);
            this->save[name] = target;
            return target;
        }
        return nullptr;
    }

    void addEdge(TreeNode* father, TreeNode* kid)
    {
        // 如果在roots发现father，把kid放在children里
        // 如果在roots发现kid，
        for (auto const& item : this->roots) {
            if (item == kid)
            {
                auto it = std::find(this->roots.begin(), this->roots.end(), item);
                if (it != this->roots.end())
                    this->roots.erase(it);
            }
        }
        father->addChildren(kid);
        kid->addFather(father);
    }


};

#endif
