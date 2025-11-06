#include <string>
#include <sstream>
#include <iostream>
#include <regex>

#include "Tree.hpp"
#include "utils.hpp"

enum TokenType
{
    NAME,
    INTEGER,
    STRING,
    AND,           // &&
    OR,            // ||
    NOT,           // !
    UNEQUAL,       // !=
    EQUAL,         // =
    LESS,          // <
    LESS_EQUAL,    // <=
    GREATER,       // >
    GREATER_EQUAL, // >=
    OPEN_BRACKET,  // [
    CLOSE_BRACKET, // ]
    OPEN_PARENT,   // (
    CLOSE_PARENT,  // ）
    END,
};

class Token
{
public:
    Token()
    {
        this->type = END;
        this->value = "";
    }

    Token(TokenType type, std::string value)
    {
        this->type = type;
        this->value = value;
    }

    TokenType getType()
    {
        return type;
    }

    std::string getValue()
    {
        return value;
    }

    void setValue(std::string value)
    {
        this->value = value;
    }

private:
    TokenType type;
    std::string value;
};

class Lexer
{
public:
    Lexer(std::string input)
    {
        this->input = input;
        this->position = 0;
    }

    Token getNextToken()
    {
        while (position < input.length())
        {
            char ch = input[position];
            if (ch == ' ' || ch == '\t')
                position++;
            else if (ch == '\n')
                break;
            else if (isalpha(ch) || isdigit(ch))
            {
                int start = position;
                while (position < input.length() && input[position] != ' ' && input[position] != '{' && input[position] != '}' && input[position] != '(' && input[position] != ')')
                    position++;
                std::string value = input.substr(start, position - start);
                if (std::regex_match(value, std::regex("[0-9]+")))
                    return Token(INTEGER, value);
                else if (std::regex_match(value, std::regex("[A-Za-z0-9_-]+")))
                    return Token(NAME, value);
                else
                    throw std::runtime_error("Unexpected character: " + ch);
            }
            else if (ch == '"')
            {
                int start = position++;
                while (position < input.length() && input[position] != '"')
                    position++;
                std::string value = input.substr(start, ++position - start);
                return Token(STRING, value);
            }
            else if (ch == '!')
            {
                if (input[position + 1] == '=')
                {
                    position += 2;
                    return Token(UNEQUAL, "!=");
                }
                else
                {
                    position++;
                    return Token(NOT, "!");
                }
            }
            else if (ch == '|')
                if (input[position + 1] == '|')
                {
                    position += 2;
                    return Token(OR, "||");
                }
                else
                    throw std::runtime_error("Unexpected character: " + ch);
            else if (ch == '&')
            {
                if (input[position + 1] == '&')
                {
                    position += 2;
                    return Token(AND, "&&");
                }
                else
                    throw std::runtime_error("Unexpected character: " + ch);
            }
            else if (ch == '=')
            {
                position += 1;
                return Token(EQUAL, "=");
            }
            else if (ch == '(')
            {
                position += 1;
                return Token(OPEN_PARENT, "(");
            }
            else if (ch == ')')
            {
                position += 1;
                return Token(CLOSE_PARENT, ")");
            }
            else if (ch == '>')
            {
                if (input[position + 1] == '=')
                {
                    position += 2;
                    return Token(GREATER_EQUAL, ">=");
                }
                else
                {
                    position++;
                    return Token(GREATER, ">");
                }
            }
            else if (ch == '<')
            {
                if (input[position + 1] == '=')
                {
                    position += 2;
                    return Token(LESS_EQUAL, "<=");
                }
                else
                {
                    position++;
                    return Token(LESS, "<");
                }
            }
            else
            {
                throw std::runtime_error("Unexpected character: " + ch);
            }
        }
        return Token(END, "");
    }

private:
    std::string input;
    int position;
};

class Parser
{
public:
    Parser(Lexer& lexer, TreeForest* forest) : lexer(lexer), forest(forest) {
        currentToken = this->lexer.getNextToken();
    }

    std::vector<TreeNode *> parser(TreeNode* kid)
    {
        std::vector<TreeNode *> list;
        while (currentToken.getType() != END)
        {
            list = toRPN(kid);
        }
        return list;
    }

private:
    Lexer lexer;
    Token currentToken;
    TreeForest* forest;

    void mergeAnd(std::vector<TreeNode *> *list, std::vector<Token> *save)
    {
        while (save->size() && save->back().getType() == AND) {
            save->pop_back();
            auto prev1 = list->back();
            list->pop_back();
            auto prev2 = list->back();
            list->pop_back();

            if (prev1->type == And) {
                forest->addEdge(prev2, prev1);
                list->emplace_back(prev1);
            } else if (prev2->type == And) {
                forest->addEdge(prev1, prev2);
                list->emplace_back(prev1);
            } else {
                TreeNode *tmp = new TreeNode(And);
                forest->addEdge(prev1, tmp);
                forest->addEdge(prev2, tmp);
                list->emplace_back(tmp);
            }
        }
    }

    void caseNAME(std::vector<TreeNode *> *list, std::vector<Token> *save, TreeNode *node, TreeNode* kid) {
        node = handle_NAME();
        if (node != nullptr) {
            list->emplace_back(node);
            node->addKid(kid);
        } else {
            if (save->size()) 
                save->pop_back();
            if (currentToken.getType() == CLOSE_PARENT)
                eat(CLOSE_PARENT); 
            if (currentToken.getType() == OR || currentToken.getType() == AND)
                eat(currentToken.getType());
        }
    }

    std::vector<TreeNode *> toRPN(TreeNode* kid)
    {
        TreeNode *node = nullptr;
        std::vector<TreeNode *> list;
        std::vector<Token> save;
        while (currentToken.getType() != END) {
            switch (currentToken.getType()) {
                case NAME:
                {
                    caseNAME(&list, &save, node, kid);
                    break;
                }
                case NOT:
                {
                    eat(NOT);
                    if (currentToken.getType() == NAME)
                    {
                        // 一般情况NOT+CONFIG不会接复杂表达式
                        caseNAME(&list, &save, node, kid);
                        if (node != nullptr)
                            node->updateInfo("NOT", "");
                    }
                    else if (currentToken.getType() == OPEN_PARENT)
                    {
                        eat(OPEN_PARENT);
                        auto result = toRPN(kid);
                        // 判断节点数量，增加信息!
                        if (result.size() == 1) {
                            TreeNode *tmp = result[0];
                            tmp->updateInfo("NOT", "");
                            list.emplace_back(tmp);
                        } else {
                            TreeNode *tmp = new TreeNode(Parent);
                            tmp->updateInfo("NOT", "");
                            for (auto item : result) {
                                tmp->addKid(item);
                            }
                            list.emplace_back(tmp);
                        }
                    }
                    break;
                }
                case OR:
                {
                    if (save.size() >= 2) {
                        mergeAnd(&list, &save);
                    }
                    save.emplace_back(currentToken);
                    eat(OR);
                    break;
                }
                case AND:
                {
                    if (list.size())
                        save.emplace_back(currentToken);
                    eat(AND);
                    break;
                }
                case OPEN_PARENT:
                {
                    eat(OPEN_PARENT);
                    auto res = toRPN(kid);
                    if (res.size() == 1) {
                        list.emplace_back(res[0]);
                    } else if (save.size() == 0) {
                        list.insert(list.end(), res.begin(), res.end());
                    } else {
                        TreeNode *tmp = new TreeNode(Parent);
                        for (auto item : res) {
                            // tmp->addKid(item);
                            forest->addEdge(tmp, item);
                        }
                        list.emplace_back(tmp);
                    }
                    break;
                }
                case CLOSE_PARENT:
                {
                    eat(CLOSE_PARENT);
                    break;
                }
                default:
                    throw std::runtime_error("Parser Error");
            }
        }
        if (save.size()) {
            mergeAnd(&list, &save);
        }
        return list;
    }

    void eat(TokenType tokenType)
    {
        if (currentToken.getType() == tokenType)
        {
            currentToken = lexer.getNextToken();
        }
        else
        {
            throw std::runtime_error("Unexpected token type: " + std::to_string(tokenType));
        }
    }

    TreeNode* handle_NAME()
    {
        Token name = currentToken;
        eat(NAME);
        TreeNode *node = forest->addNode(name.getValue(), Null);
        if (currentToken.getType() == UNEQUAL || \
            currentToken.getType() == EQUAL || \
            currentToken.getType() == LESS || \
            currentToken.getType() == LESS_EQUAL || \
            currentToken.getType() == GREATER || \
            currentToken.getType() == GREATER_EQUAL)
        {
            Token op = currentToken;
            eat(currentToken.getType());
            if (currentToken.getType() == NAME || \
                currentToken.getType() == INTEGER || \
                currentToken.getType() == STRING)
            {
                // 更新节点信息
                if (node)
                    node -> updateInfo(op.getValue(), currentToken.getValue());
                eat(currentToken.getType());
                return node;
            }
            else 
                throw std::runtime_error("Parser Error");
        }
        else if (currentToken.getType() == AND || \
                 currentToken.getType() == OR || \
                 currentToken.getType() == END)
        {
            return node;
        }
        else if (currentToken.getType() == CLOSE_PARENT) {
            return node;
        }
        else {
            throw std::runtime_error("Parser Error");
        }
    }
};

void handleLine(const std::string& line, TreeForest *forest, TreeNode *Kid, std::vector<TreeNode*> prev) {
    Lexer lexer(line);
    Parser parser(lexer, forest);
    auto res = parser.parser(Kid);
    for (auto item : res) {
        forest->addEdge(item, Kid);
    }
    if (prev.size()) {
        for(auto item : prev) {
            for (auto child : res) {
                forest->addEdge(item, child);
            }
        }
    }
    prev = res;
}

void handleDepend(auto depends, TreeForest *forest, TreeNode *Kid, auto prev) {
    std::string dep;
    for (auto item : depends) {
        std::string tmp(item);
        if (tmp[0] != '$') {
            if (dep.size() > 0) dep += " && ";
            dep += std::string(tmp);
        }
    }
    if (dep.size())
        handleLine(dep, forest, Kid, prev);
}

void handleDetail(auto target, const std::string& flag, const std::string& nodeName, TreeForest *forest, TreeNode *Kid) {
    for (int index = 0; index < target.size(); ++index) {
        std::string tmp(target[index]);
        auto res = split(tmp, " if ");
        if (res.size() == 2)
            forest->updateDetail(nodeName, res[0], res[1], flag);
        else if (res.size() == 1)
            forest->updateDetail(nodeName, res[0], "", flag);
    }
}

void parser(const std::string& path, TreeForest *forest)
{
    std::ifstream file(path);
    json data = json::parse(file);

    for (auto name : forest->getArchNode()) {
        std::cout << name << std::endl;
        for (const auto& item : data[name]) {
            TreeNode* Kid = forest->addNode(name, convertType(item["type"]));
            std::vector<TreeNode*> prev;
            for (const auto& group : item["group"]) {
                std::string type(group["type"]);
                if (type.compare("menu") == 0) {
                    handleDepend(group["depends"], forest, Kid, prev);
                } else if (type.compare("if") == 0) {
                    if (group["depends"].size())
                        handleLine(group["depends"], forest, Kid, prev);
                } else if (type.compare("bool") == 0 || type.compare("tristate") == 0) {
                    std::string choiceName(group["name"]);
                    if (choiceName.substr(0,6).compare("choice") == 0) {
                        TreeNode *choice = forest->updateChoice(choiceName, Kid);
                        if (prev.size()) {
                            for(auto item : prev) {
                                forest->addEdge(item, choice);
                            }
                        }
                        prev.clear();
                        prev.emplace_back(choice);
                        handleDepend(group["depends"], forest, Kid, prev);
                        handleDetail(group["default"], "Default", name, forest, Kid);
                        continue;
                    } else
                        exit(-1);
                }
            }
            // select
            handleDetail(item["value"]["select"], "select", name, forest, Kid);
            handleDepend(item["value"]["depends"], forest, Kid, prev);
            handleDetail(item["value"]["default"], "default", name, forest, Kid);
            handleDetail(item["value"]["range"], "range", name, forest, Kid);
        }
    }
}
