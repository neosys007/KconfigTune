import subprocess
import os
import re
import pandas as pd

sysctl_file = './input.txt'
output_file = "modification_results.txt"
with open(output_file, 'w') as file:
    file.write("")

# 初始化要修改的参数列表
with open(sysctl_file, 'r') as f:
    lines = f.readlines()
    sysctl_df = pd.DataFrame({
            'name': [line.strip().split('=')[0].strip() for line in lines],
            'param': [line.strip().split('=')[0].strip().split('.')[-1] for line in lines],
            'category': [line.strip().split('=')[0].strip().split('.')[-2] for line in lines],
            'value': [line.strip().split('=')[1].strip() if line.strip().split('=')[1].strip() else 'NAN' for line in lines]
        })
    
#函数功能描述：修改某个sysctl参数，并验证是否修改成功
#input描述：sysctl参数名<param_name> 要修改的成的值<value>
#output描述：若该值能成功修改,则返回true,否则返回false
def sysctl_set(param_name, value):
    modified_value = str(value)
    try:
        # 设置参数
        set_command = f"sysctl -w {param_name}={modified_value}"
        subprocess.run(set_command, shell=True, check=True)

        # 验证参数
        check_command = f"sysctl -n {param_name}"
        result = subprocess.run(check_command, shell=True, check=True, capture_output=True, text=True)

        # 检查设置的值是否正确
        if result.stdout.strip() == modified_value:
            return True
        else:
            return False

    except subprocess.CalledProcessError as e:
        return False

    
#函数功能描述：查找参数可修改的上限
#input描述：sysctl参数名<param_name> 要修改的成的值<value>
#output描述：若该值能成功修改,则返回true,否则返回false
def find_bound():
    # 用于存储修改结果
    results = []

    for index, row in sysctl_df.iterrows():
        param_name = row['name']
        try:
            current_value = int(row['value'])
            lower_bound = current_value + 1
            upper_bound = 2**31 - 1  # 假设上限是int的上限，32位有符号整数的最大值
        except ValueError:
            results.append((param_name, 'Invalid value, cannot modify'))
            continue
        
        #二分查找的过程，每次都调用sysctl_set
        while lower_bound <= upper_bound:
            mid_value = (lower_bound + upper_bound) // 2
            if sysctl_set(param_name, mid_value):
                current_value = mid_value
                lower_bound = mid_value + 1
            else:
                upper_bound = mid_value - 1

        # 如果能修改
        if sysctl_set(param_name, current_value):
            # 记录最终结果
            results.append((param_name, f"Upper limit is {current_value}"))
            # 将结果写入文件
            with open(output_file, 'a') as file:
                file.write(f"{param_name} = {str(current_value)}\n")
        else :
            results.append((param_name, f"Modification failed"))

    # 将结果添加到DataFrame
    results_df = pd.DataFrame(results, columns=['name', 'result'])

    # 保存结果到CSV文件
    results_df.to_csv('sysctl_modification_results.csv', index=False, encoding='utf-8')


find_bound()