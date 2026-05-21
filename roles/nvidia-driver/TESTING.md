# NVIDIA Driver Role 快速测试指南

## 🎯 目标

在 k8s-gpu-worker-1 (10.17.3.30) 上安装 NVIDIA GPU 驱动，验证 VFIO GPU 直通虚拟机中的驱动安装流程。

## 📋 前置检查

```bash
# 1. 确认 inventory.ini 中有 gpu-workers 组
cat /home/dylan/workspace/infrastructure/setup-k8s/inventory.ini | grep -A 5 "gpu-workers"

# 预期输出：
# [gpu-workers]
# k8s-gpu-worker-1 ansible_host=10.17.3.30

# 2. 确认节点可以 SSH 访问
ssh user@10.17.3.30 "echo 'SSH connection successful'"

# 3. 确认节点有 NVIDIA GPU 硬件
ssh user@10.17.3.30 "lspci | grep -i nvidia"

# 预期输出：
# 00:08.0 VGA compatible controller: NVIDIA Corporation AD104GL [RTX 4000 Ada Generation]
```

## 🚀 执行安装

### 方法 A：使用专用 playbook（推荐用于首次测试）

```bash
cd /home/dylan/workspace/infrastructure/setup-k8s

# 执行驱动安装
ansible-playbook -i inventory.ini playbook-nvidia-driver.yml -v
```

**预期输出**：
```
TASK [Display GPU detection status]
✅ NVIDIA GPU detected: 00:08.0 VGA compatible controller: NVIDIA Corporation AD104GL [RTX 4000 Ada Generation]
Proceeding with driver installation...

TASK [Install via ubuntu-drivers autoinstall]
changed: [k8s-gpu-worker-1]

TASK [Reboot the system]
changed: [k8s-gpu-worker-1]

TASK [Display driver installation result]
✅ NVIDIA driver installation completed successfully!

+-----------------------------------------------------------------------------+
| NVIDIA-SMI 550.54.14    Driver Version: 550.54.14    CUDA Version: 12.4     |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  RTX 4000 Ada ...    Off  | 00000000:00:08.0 Off |                  Off |
+-------------------------------+----------------------+----------------------+
```

### 方法 B：通过 join playbook 自动安装

```bash
# 如果重新加入 GPU 节点，会自动安装驱动
ansible-playbook -i inventory.ini playbook-join.yml \
  --extra-vars "target_hosts=gpu-workers nct_enabled=true"
```

## ✅ 验证安装

### 1. 检查驱动状态

```bash
ssh user@10.17.3.30 "nvidia-smi"
```

**预期输出**：显示 GPU 信息、驱动版本、显存等

### 2. 检查内核模块

```bash
ssh user@10.17.3.30 "lsmod | grep nvidia"
```

**预期输出**：
```
nvidia_uvm           3145728  0
nvidia_drm            131072  0
nvidia_modeset       1572864  1 nvidia_drm
nvidia              67108864  2 nvidia_uvm,nvidia_modeset
```

### 3. 检查已安装的包

```bash
ssh user@10.17.3.30 "dpkg -l | grep nvidia-driver | grep '^ii'"
```

**预期输出**：
```
ii  nvidia-driver-550                 550.54.14-0ubuntu0.24.04.1      amd64        NVIDIA driver metapackage
```

## 🔧 故障排查

### 问题 1：GPU 未检测到

```bash
# 检查 lspci 输出
ssh user@10.17.3.30 "lspci | grep -i nvidia"

# 如果没有输出，检查：
# 1. VFIO 配置是否正确
# 2. 虚拟机 BIOS 设置
# 3. IOMMU 是否启用
```

### 问题 2：驱动安装失败

```bash
# 查看详细日志
ssh user@10.17.3.30 "cat /var/log/apt/term.log | tail -50"

# 常见解决方案：
# 1. 更新系统
ssh user@10.17.3.30 "sudo apt update && sudo apt upgrade -y"

# 2. 清理旧驱动
ssh user@10.17.3.30 "sudo apt purge nvidia-* -y"

# 3. 重试安装
ansible-playbook -i inventory.ini playbook-nvidia-driver.yml
```

### 问题 3：重启后 nvidia-smi 不可用

```bash
# 检查服务状态
ssh user@10.17.3.30 "systemctl status nvidia-persistenced"

# 检查 dmesg
ssh user@10.17.3.30 "dmesg | grep -i nvidia | tail -20"

# 手动加载模块
ssh user@10.17.3.30 "sudo modprobe nvidia"
```

## 📊 下一步：安装 Container Toolkit

驱动安装成功后，继续安装 NVIDIA Container Toolkit：

```bash
# 运行完整的 plugin 安装
ansible-playbook -i inventory.ini playbook-plugins.yml \
  -e "k8s_plugins_only=nvidia-device-plugin"

# 这将依次执行：
# 1. nvidia-driver (已安装，跳过)
# 2. nvidia-container-toolkit
# 3. nvidia-device-plugin (Kubernetes DaemonSet)
```

## 🎉 成功标志

完成所有步骤后，你应该看到：

```bash
# 1. 驱动正常工作
ssh user@10.17.3.30 "nvidia-smi"  # ✅ 显示 GPU 信息

# 2. Container Toolkit 已配置
ssh user@10.17.3.30 "containerd config dump | grep nvidia"  # ✅ 显示 nvidia runtime

# 3. Kubernetes Device Plugin 运行中
kubectl get pods -n nvidia-device-plugin  # ✅ Pod Running

# 4. GPU 资源可调度
kubectl describe node k8s-gpu-worker-1 | grep nvidia.com/gpu  # ✅ 显示 GPU 容量
```

## 💡 提示

- **首次安装建议使用方法 A**（专用 playbook），便于观察详细输出
- **生产环境使用方法 B**（集成到 join workflow），实现自动化
- **驱动版本会根据硬件自动选择**，无需手动指定
- **安装过程会自动重启**，确保驱动正确加载
