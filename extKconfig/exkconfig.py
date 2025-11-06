import os
import re
import pandas as pd
import subprocess

# 请给出linux源码的绝对路径
kernel_source_dir = '/home/sunying/focal'
# 请给出输入的sysctl_list
sysctl_file = './input.txt'

if os.path.exists('all_variables.txt'):
    "All variables has been found"
else:
    print(f"Find all variables ...")
    ctags_command = f"find {kernel_source_dir} -type f \( -name \"*.c\" -o -name \"*.h\" \) -print | ctags --fields=+a -x --c-kinds=v --languages=C,C++ -I __read_mostly -L - > all_variables.txt"
    subprocess.run(ctags_command, shell=True, check=True)

sysctl_df = pd.DataFrame(columns=['name', 'param', 'category', 'value', 'insert'])
ip_df = pd.read_csv('./ip_df.csv', index_col=False)
sysctl_ip = pd.DataFrame(columns=ip_df.columns)
# 使用with语句打开文件并填充DataFrame
with open(sysctl_file, 'r') as f:
    lines = f.readlines()
    for line in lines:
        name = line.strip().split('=')[0].strip()
        up_name = name.rsplit('.', 1)[0]
        param = name.split('.')[-1]
        category = name.split('.')[-2]
        value = line.strip().split('=')[1].strip() if len(line.strip().split('=')) > 1 else 'NAN'
        # 如果是ipv4和ipv6模块
        if up_name in ['net.ipv4.conf.all', 'net.ipv4.conf.default', 'net.ipv6.conf.default', 'net.ipv6.conf.all']:
            matching_row = ip_df[ip_df['name'] == name].copy()
            if not matching_row.empty:
                # 修改新的 DataFrame
                matching_row['value'] = int(value)
                # 替换文件地址
                matching_row['path2'] = matching_row['path2'].astype(str).str.replace("target_path", kernel_source_dir, regex=False)
                # 仅在新的 DataFrame 上进行修改后再进行合并

                matching_row = matching_row.dropna(axis=1, how='all')
                sysctl_ip = pd.concat([sysctl_ip, matching_row], ignore_index=True)
            continue

        sysctl_df = sysctl_df._append({
            'name': name,
            'param': param,
            'category': category,
            'value': value,
            'insert': False,
        }, ignore_index=True)

sysctl_ip.loc[:, 'row2'] = pd.to_numeric(sysctl_ip['row2'], errors='coerce')

def find_procname():
    #函数功能描述：扫描整个linux源码，找到所有给procname注册的地方，并保存为csv用于后续
    #input描述：无
    #output描述：输出一个csv文件，all_procname.csv，包含所有的.procname行号，文件路径
    #其他：默认不运行，因为这段代码运行比较费时间，同时已经保存了csv文件

    all_param = pd.DataFrame(columns=['param', 'path', 'row', 'category'])
    # 在全局找procname字段
    for root, _, files in os.walk(kernel_source_dir):
        for file in files:    
            if file.endswith('.c'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', errors='ignore') as f:
                    content = f.readlines()  # 读取所有行到一个列表中
                    for lineno, line in enumerate(content, 1):  # 从1开始计数行号
                        if line.strip().startswith('.procname'):
                            new_data = {'param': line.strip().split()[2].strip('"')[:-2],
                                        'path': file_path, 'row': lineno, 'category': file_path.split('/')[-2]}
                            all_param = pd.concat([all_param, pd.DataFrame([new_data])], ignore_index=True)
    all_param.to_csv('all_procname.csv', index=False, encoding='utf-8')

# 判断是否已经找过所有的procname，找过则不运行find_procname()，因为这一段代码运行很耗时
if os.path.exists('all_procname.csv'):
    print(f"All procnames has been found")
else:
    print(f"Find all procnames ...")
    find_procname()


print("Find used procnames ...")
#函数功能描述：根据所有的procname文件，去匹配要修改的pd中的name项,并保存
#input描述：前面生成的all_procname.csv，以及sysctl_df
#output描述：根据sysctl_df中的param字段，在all_procname.csv找到注册的c文件路径以及行号，填充进sysctl_df中

all_param = pd.read_csv('./all_procname.csv')

# 创建一个哈希表，实现对pandas中param的映射
proc_hash = {}

# 填充嵌套哈希表
for idx, (param, category) in enumerate(zip(sysctl_df['param'], sysctl_df['category'])):
    # 如果 param 不在 hash_map 中，直接添加
    if param not in proc_hash:
        proc_hash[param] = {(idx, category)}
    else:
        # 如果 param 已经在 hash_map 中，添加新的 (idx, category)
        proc_hash[param].add((idx, category))

for index, row in all_param.iterrows():
    key = row['param']
    category = row['category']
    # 判断key是否在哈希表中
    if key in proc_hash:
        row_index = -1
        for idx, cat in proc_hash[key]:
            if len(proc_hash[key]) == 1:
                row_index = idx
            elif cat == category:
                row_index = idx
                break
        if row_index == -1 :
            #print("no:" + key + ' ' + category)
            continue
        sysctl_df.at[row_index, 'path1'] = row['path']
        sysctl_df.at[row_index, 'row1'] = row['row']

# 添加用户字典
userdict = {'fs.epoll.max_user_watches': ('/home/sunying/focal/fs/eventpoll.c', 323)}

for index, row in sysctl_df.iterrows():
    key = row['name']
    # 判断key是否在哈希表中
    if key in userdict:
        file_path, row_number = userdict[key]
        # 更新DataFrame中的列
        sysctl_df.at[index, 'path1'] = file_path
        sysctl_df.at[index, 'row1'] = row_number

sysctl_df.to_csv('temp.csv', index=False, encoding='utf-8')

# 开始找具体起作用的变量名称，用于后续的修改流程。
print("Find variables name ...")
# 转数字
sysctl_df['row1'] = pd.to_numeric(sysctl_df['row1'], errors='coerce')
# 删除包含 NaN 的行
sysctl_df = sysctl_df.dropna(subset=['row1'])
# 直接将 'row1' 列转换为整数类型
sysctl_df['row1'] = sysctl_df['row1'].astype(int)
# 将列转换为整数类型
sysctl_df['row1'] = sysctl_df['row1'].astype(int)
for index, row in sysctl_df.iterrows():
    if row['path1']:
        file_path = row['path1']
        lineno = row['row1']
        with open(file_path, 'r', errors='ignore') as f:
            f.seek(0)  # 重置文件指针到文件开头
            lines = f.readlines()  # 读取所有行到一个列表中
            # 从.procname所在行的下一行开始，向后搜索最多7行
            for i in range(lineno, min(lineno + 8, len(lines))):
                # 检查行是否以非空白字符开头，并且包含.data
                if lines[i].strip().startswith('.data'):
                    parts = lines[i].split('=')[1].strip().replace('&', '')
                    variable_name = parts[: -1]
                    sysctl_df.loc[index, 'variable_name'] = variable_name
                    break  # 找到第一个匹配项后停止搜索

print("Find the code location of the variable ...")
# 分两种情况，结构体，和直接赋值       
sysctl_df['variable_name'] = sysctl_df['variable_name'].astype(str)
def find_struct(directory_path, index, pattern):
    flag = False
    for root,_, files in os.walk(directory_path):
        for file in files:
        #拼接完整的文件路径
            file_path_full = os.path.join(root, file)
            if file_path_full.endswith('.c'):
            #现在 file path 包含了目录中所有文件的完整路径
                with open(file_path_full,'r',errors='ignore') as f:
                    lines = f.readlines()
                    for lineno, line in enumerate(lines, 1):
                        if pattern.search(line):
                            # 向上查找200行
                            for i in range(0, 1000):
                                prev_line_no = lineno - i
                                if prev_line_no > 0 :
                                    if struct_name in lines[prev_line_no]:
                                        flag = True
                                        #找到初始化，记录文件路径、行号和初始化行
                                        sysctl_df.at[index,'path2'] = file_path_full
                                        sysctl_df.at[index,'row2']  = lineno
                                        sysctl_df.at[index,"line"]  = line.strip()
                                        break 
                            if flag :
                                break
    return flag

# 遍历sysctl_df
# 直接变量的变量会存到该hash_map中

# 重置索引
sysctl_df = sysctl_df.reset_index(drop=True)
sysctl_df.to_csv('output_test.csv', index=False, encoding='utf-8')

hash_map = {}
for index in range(len(sysctl_df)):
    row = sysctl_df.iloc[index]
    if '.' not in row['variable_name']:
        hash_map[row['variable_name']] = index
        continue
    variable_name = row['variable_name'].split('.')[-1]
    struct_name = row['variable_name'].split('.')[-2]

    if pd.isna(variable_name):
        continue
    file_path = row['path1']
    directory_path = os.path.dirname(file_path)
    pattern=re.compile(r'\.' + re.escape(variable_name) + r'.*=')
    flag = find_struct(directory_path, index, pattern)           
    if not flag :
        flag = find_struct(kernel_source_dir, index, pattern)
        
    if not flag:
        for prev_index in range(len(sysctl_df)):
            if prev_index >= 0 :
                pre_row = sysctl_df.iloc[int(prev_index)]
                if '.' not in pre_row['variable_name']:
                    continue
                pre_variable_name = pre_row['variable_name'].split('.')[-1]
                pre_struct_name = pre_row['variable_name'].split('.')[-2]
                if struct_name == pre_struct_name:
                    new_line = str(str(pre_row['line']).replace(pre_variable_name, variable_name))
                    #记录文件路径、行号和初始化行
                    sysctl_df.at[index,'path2'] = pre_row['path2']
                    sysctl_df.at[index,'row2']  = pre_row['row2']
                    sysctl_df.at[index,"line"]  = new_line
                    sysctl_df.at[index,"insert"] = True
                    break

print(hash_map)
input_file = 'input.txt'

with open(input_file, 'r', encoding='utf-8') as file:
    for line in file:
        elements = line.split()
        if elements:
            key = elements[0]
            # 判断key是否在哈希表中
            if key in hash_map:
                # 获取DataFrame中对应的行索引
                row_index = hash_map[key]
                sysctl_df.loc[row_index, 'path2'] = elements[3]
                sysctl_df.loc[row_index, 'row2'] = int(elements[2])
                sysctl_df.loc[row_index, 'line'] = ' '.join(elements[4:])

print("Modify code ...")

def modify_code(sysctl_df):
    #函数功能描述：根据前面找到的.data全局变量初始化位置进行修改源码
    #input描述：sysctl_df
    #output描述：去修改对应的linux源码，并且创建一个新的kconfig目录。
    file_groups = sysctl_df.groupby('path2')
    sysctl_df.loc[:, 'row2'] = pd.to_numeric(sysctl_df['row2'], errors='coerce')
    # 删除包含 NaN 的行
    sysctl_df = sysctl_df.dropna(subset=['row2'])
    sysctl_df.to_csv('output.csv', index=False, encoding='utf-8')
    sysctl_df = pd.read_csv('./output.csv')
    notsupport_rows = []
    for file_path, group in file_groups:
        insert_rows = []
        if not file_path:  # 如果file_path为空、None或空字符串，则跳过
            continue
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        # 对每个文件中的修改按行号排序
        for _, row in group.sort_values(by='row2').iterrows():
            lineno = row['row2'] - 1
            param = row['name']
            value = row['value']
            # 修改指定行的内容
            line = row['line']
            equal_index = line.find('=')
            if equal_index != -1:
                # 截取 '=' 之前和之后的部分
                before_equal = line[:equal_index + 1]
                if line[-1] == ',':
                    after_equal = ",\n"
                else :
                    after_equal = ";\n" 
                # 构造新的行
                new_line = before_equal + " CONFIG_USER_" + param.upper().replace(".", "_").replace("-", "_") + after_equal
                if row['insert']:
                    insert_rows.append((int(row['row2']), new_line))
                else:   
                    lines[int(lineno)] = new_line
            
            
            # 再修改kconfig文件
            kconfig_file_path = kernel_source_dir + "/exKconfig/Kconfig"
            new_lines = ["","config USER_"+  param.upper().replace(".", "_").replace("-", "_"), "    int " + '"exKconfig of ' + param + '"',  "    default " + str(value)]        
            new_content = '\n'.join(new_lines) + '\n'
            new_content_lines = new_content.splitlines(keepends=True)
            
            # 使用'a'模式打开文件，追加内容
            with open(kconfig_file_path, 'r', encoding='utf-8') as kconfig_file:
                original_content = kconfig_file.readlines()

            insert_position = 1

            # 在指定位置插入新内容
            updated_content = original_content[:insert_position] + new_content_lines + original_content[insert_position:]
            
            # 将更新后的内容写回文件
            with open(kconfig_file_path, 'w', encoding='utf-8') as kconfig_file:
                kconfig_file.writelines(updated_content)
        

        # 集中插入部分
        # 对insertions按照行号进行排序，确保最大的行号在前，然后倒序插入
        for lineno, new_line in sorted(insert_rows, key=lambda x: -x[0]):
            # 在lines列表中插入new_line，index为原始行号
            lines.insert(lineno, new_line)
        # 头文件部分
        new_lines = ["#ifndef CONFIG_USER_" + param.upper().replace(".", "_").replace("-", "_"), "    #include <generated/autoconf.h>", "#endif"]
        new_content = '\n'.join(new_lines) + '\n'
        new_content_lines = new_content.splitlines(keepends=True)
        

        # 确定插入位置，第一个include之前
        insert_position = 0
        for i, line in enumerate(lines):
            if  line.strip().startswith('#include'):
                insert_position = i
                break

        # 在指定位置插入新内容
        lines = lines[:insert_position] + new_content_lines + lines[insert_position:]
        

        # 将修改后的内容写回文件
        with open(file_path, 'w', encoding='utf-8') as file:
            file.writelines(lines)
                
sysctl_df.to_csv('output.csv', index=False, encoding='utf-8')
sysctl_ip.to_csv('output_ip.csv', index=True, encoding='utf-8')
modify_code(sysctl_ip)
modify_code(sysctl_df)

print("Done ")
