'''此函数用于获取所有config配置项的help信息
函数逻辑是
  首先需要将涉及到的所有Kconfig文件整理到一个文件内（getAllFile.py）
  其次抽取config的信息, 生成json文件
  最后抽取config得help信息, 生成json文件
依次生成 tag_arch.Kconfig -> tag_arch_config.json -> tag_arch_help.json
建议使用默认文件名

此函数需要将所有Kconfig函数整理到一个文件内, 借助HandleKconfig函数完成
如果已经完成此操作, 可以注释32行, 直接运行33行, 调用parser函数
函数将直接使用默认的文件名tag + _ + arch + .Kconfig

在初筛所有Kconfig的过程中
过滤掉Documentation, scripts/kconfig
对于arch路径下的, 搜索指定架构目录下的所有Kconfig文件
'''
import tools

if __name__ == '__main__':
    target = ""
    save = ""
    tools.get_help(target, save)
