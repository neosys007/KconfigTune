#include <iostream>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

int main()
{
    // 创建一个JSON对象
    json j;
    j["name"] = "John";
    j["age"] = 30;
    j["isStudent"] = true;

    // 输出JSON对象
    std::cout << j.dump() << std::endl;

    // 从JSON字符串中读取JSON对象
    std::string jsonString = R"({"age":30,"isStudent":true,"name":"John","test":{"age":25,"isStudent":false,"name":"Mary"}})";
    json j2 = json::parse(jsonString);
    std::cout << j2.dump() << std::endl;

    j["test"] = j2;

    std::cout << j.dump() << std::endl;

    // 访问JSON对象的属性
    std::cout << j2["name"] << " is " << (j2["isStudent"] ? "a student" : "not a student") << std::endl;

    return 0;
}
