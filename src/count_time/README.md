# 利用C++构建AST语法树

读取dep.json构建多叉树森林，描述Kconfig配置项的上下游关系

## 相关数据结构

```
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
}

class TreeForest
{
    std::string tmpFile;
    std::vector<TreeNode *> roots;
    std::unordered_map<std::string, TreeNode *> save;
    std::vector<std::string> ArchNodes;
    std::unordered_map<std::string, std::string> change;

    std::unordered_map<std::string, TreeNode *> choice;
}
```

## 实现的功能



## Todo

* 实现移动语义
* 序列化+反序列化