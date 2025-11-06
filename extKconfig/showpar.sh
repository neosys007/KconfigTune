#!/bin/bash

# 需要root权限
if [ "$EUID" -ne 0 ]; then
    echo "请使用sudo运行此脚本"
    exit
fi

# 新的参数列表
PARAMS=(
    # 文件系统参数
    
    # TCP协议栈配置
    "net.ipv4.tcp_tw_reuse"
    "net.ipv4.tcp_syncookies"
    "net.ipv4.ip_local_port_range"
    "net.ipv4.tcp_max_tw_buckets"
    "net.ipv4.tcp_max_orphans"
    "net.ipv4.tcp_max_syn_backlog"
    "net.ipv4.tcp_timestamps"
    "net.ipv4.tcp_synack_retries"
    "net.ipv4.tcp_syn_retries"
    "net.ipv4.tcp_fin_timeout"
    "net.ipv4.tcp_keepalive_time"
    "net.ipv4.tcp_mem"
    "net.ipv4.tcp_rmem"
    "net.ipv4.tcp_wmem"
    
    # 网络核心参数
    "net.core.somaxconn"
    "net.core.netdev_max_backlog"
    "net.core.wmem_default"
    "net.core.rmem_default"
    "net.core.rmem_max"
    "net.core.wmem_max"
    "net.core.netdev_budget"
    "net.core.optmem_max"
)

# 检查每个参数
echo "当前系统参数状态："
echo "----------------------------------------"
for param in "${PARAMS[@]}"; do
    value=$(sysctl -n $param 2>/dev/null)
    printf "%-32s = %s\n" "$param" "$value"
done

# 特殊参数验证
echo "----------------------------------------"
echo "[端口范围验证]"
ip_local_port_range=($(sysctl -n net.ipv4.ip_local_port_range))
if [ ${#ip_local_port_range[@]} -eq 2 ]; then
    echo "可用TCP端口范围：${ip_local_port_range[0]} - ${ip_local_port_range[1]}"
else
    echo "错误：ip_local_port_range 格式异常"
fi

echo "[内存缓冲验证]"
printf "TCP接收缓冲：%dMB\n" $(( $(sysctl -n net.core.rmem_max) / 1024 / 1024 ))
printf "TCP发送缓冲：%dMB\n" $(( $(sysctl -n net.core.wmem_max) / 1024 / 1024 ))