# Kubernetes 生产环境 GPU 节点接入与隔离指南

## 📋 目录

- [1. 背景与现状](#1-背景与现状)
- [2. 核心隔离机制](#2-核心隔离机制-taint-污点--affinity-亲和性)
- [3. GPU 节点标准接入工作流](#3-gpu-节点标准接入工作流)
- [4. 运维检查清单](#4-运维检查清单-checklist)
- [5. 故障排查](#5-故障排查)
- [6. 最佳实践](#6-最佳实践)

---

## 1. 背景与现状

### 集群架构

当前 Kubernetes 集群包含以下节点类型：

| 节点类型 | 节点名称 | 用途 | 状态 |
|---------|---------|------|------|
| Control Plane | `k8s-controller-1` | 集群控制平面 | Ready |
| Worker Nodes | `k8s-worker-1/2/3` | 普通业务负载 | Ready |
| **GPU Node** | **`k8s-gpu-worker-1`** | **GPU 专用计算** | **NotReady → Ready** |

### 目标

确保集群调度逻辑的严谨性，防止普通业务负载因资源匹配而漂移至 GPU 节点，实现：
- ✅ **逻辑隔离**：普通 Pod 不会调度到 GPU 节点
- ✅ **资源专享**：GPU 任务准确落地到 GPU 节点
- ✅ **安全可控**：通过 Taint/Toleration 机制精确控制调度行为

---

## 2. 核心隔离机制：Taint (污点) 与 Affinity (亲和性)

在 Kubernetes 调度模型中，**污点**与**亲和性**是实现节点逻辑隔离的黄金组合。

### 🛡️ Taint (污点) - "拦截器"

**作用**：阻止未授权的普通 Pod 调度到 GPU 节点

```bash
# 语法格式
kubectl taint nodes <node-name> <key>=<value>:<effect>

# 实际示例
kubectl taint nodes k8s-gpu-worker-1 gpu-node=true:NoSchedule
```

**Effect 说明**：
- `NoSchedule`：不调度新 Pod（已运行的 Pod 不受影响）
- `PreferNoSchedule`：尽量避免调度（软限制）
- `NoExecute`：驱逐已运行的 Pod（硬限制）

### 🎯 Affinity (亲和性) - "导航员"

**作用**：强制 GPU 任务准确落地到 GPU 节点，并申请 GPU 资源

**两种类型**：
- **Node Affinity**：基于节点标签选择节点
- **Pod Affinity/Anti-Affinity**：基于其他 Pod 的位置调度

---

## 3. GPU 节点标准接入工作流

### ⚠️ 重要提示

本工作流中的**前置条件**必须在 GPU 节点加入 Kubernetes 集群**之前**完成。
污点打标等隔离配置应在节点加入集群后、变为 `Ready` 状态前立即执行，以确保调度器绝不会将普通业务分配给该节点。

---

### 前置条件：安装 NVIDIA 驱动和 Container Toolkit

**在将 GPU 节点加入 Kubernetes 集群之前**，必须先在节点上安装 NVIDIA 驱动和 Container Toolkit。

#### 方法 A：使用 Ansible 自动化安装（推荐）

```bash
# 1. 确保 inventory.ini 中定义了 gpu-workers 组
cat >> inventory.ini << EOF

[gpu-workers]
k8s-gpu-worker-1 ansible_host=10.17.3.30
EOF

# 2. 执行驱动安装 playbook
ansible-playbook -i inventory.ini playbook-nvidia-driver.yml

# 3. 验证驱动安装
ssh user@k8s-gpu-worker-1 "nvidia-smi"
```

**工作原理**：
1. `nvidia-driver` role 自动检测 GPU 硬件
2. 使用 `ubuntu-drivers autoinstall` 安装推荐驱动
3. 可选自动重启系统
4. 验证驱动加载成功

#### 方法 B：手动安装（快速测试）

```bash
# SSH 到 GPU 节点
ssh user@k8s-gpu-worker-1

# 1. 安装推荐的 NVIDIA 驱动
sudo ubuntu-drivers autoinstall

# 2. 重启系统
sudo reboot

# 3. 重启后验证驱动
nvidia-smi

# 4. 安装 NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 5. 配置 containerd
sudo nvidia-ctk runtime configure --runtime=containerd
sudo systemctl restart containerd
```

---

### 第一步：接入与即时隔离 (防止自动调度)

在新节点加入集群后的**第一瞬间**，即使节点处于 `NotReady` 状态，也应立即执行污点打标，确保调度器绝不会将旧业务分配给该节点。

```bash
# 执行污点打标，拒绝所有不具备容忍度的 Pod
kubectl taint nodes k8s-gpu-worker-1 gpu-node=true:NoSchedule
```

**验证命令**：
```bash
kubectl get nodes k8s-gpu-worker-1 -o jsonpath='{.spec.taints}'
# 预期输出: [{"key":"gpu-node","value":"true","effect":"NoSchedule"}]
```

---

### 第二步：资源标记 (便于调度筛选)

为节点打上标签，方便后续通过 `nodeAffinity` 进行精确调度：

```bash
kubectl label nodes k8s-gpu-worker-1 gpu=true
```

**验证命令**：
```bash
kubectl get nodes k8s-gpu-worker-1 --show-labels
# 预期输出包含: gpu=true
```

**可选标签**（根据实际需求添加）：
```bash
# GPU 型号标记
kubectl label nodes k8s-gpu-worker-1 gpu-model=A100

# GPU 数量标记
kubectl label nodes k8s-gpu-worker-1 gpu-count=8

# 业务区域标记
kubectl label nodes k8s-gpu-worker-1 zone=gpu-compute
```

---

### 第三步：部署 NVIDIA Device Plugin (自动化流程)

**重要**：当启用 `nvidia-device-plugin` 时，Ansible 会自动按以下顺序执行：

```
执行顺序（自动）:
1. nvidia-driver role          # 在所有 gpu-workers 节点安装显卡驱动
   ↓
2. nvidia-container-toolkit    # 配置 containerd GPU 支持
   ↓
3. nvidia-device-plugin Helm   # 部署 Kubernetes Device Plugin
```

#### 方法 A：使用 plugin playbook（推荐）

```bash
# 一键完成所有 NVIDIA 组件安装
ansible-playbook -i inventory.ini playbook-plugins.yml \
  -e "k8s_plugins_only=nvidia-device-plugin"
```

**执行过程**：
1. ✅ 在 `gpu-workers` 组的所有节点上安装 NVIDIA 驱动
2. ✅ 在 `gpu-workers` 组的所有节点上安装 Container Toolkit
3. ✅ 在 controller 节点上部署 NDP Helm Chart
4. ✅ 等待 DaemonSet Ready

#### 方法 B：分步执行（调试用）

```bash
# Step 1: 单独安装驱动（可选，用于测试）
ansible-playbook -i inventory.ini playbook-nvidia-driver.yml

# Step 2: 单独安装 Container Toolkit（可选）
cd /home/dylan/workspace/infrastructure/setup-k8s
ansible-playbook -i inventory.ini -e "target_hosts=gpu-workers nct_enabled=true" \
  roles/nvidia-container-toolkit/tasks/main.yml

# Step 3: 仅部署 NDP Helm Chart（跳过驱动和 toolkit）
ansible-playbook -i inventory.ini playbook-plugins.yml \
  -e "k8s_plugins_only=nvidia-device-plugin" \
  --skip-tags "plugin-nvidia-device-plugin-preinstall"
```

#### 验证安装

```bash
# 检查 Driver 状态
ssh user@k8s-gpu-worker-1 "nvidia-smi"

# 检查 Container Toolkit 配置
ssh user@k8s-gpu-worker-1 "containerd config dump | grep nvidia"

# 检查 DaemonSet 状态
kubectl get ds -n nvidia-device-plugin

# 检查节点 GPU 资源
kubectl describe node k8s-gpu-worker-1 | grep -A 5 "Allocatable:"
# 预期看到: nvidia.com/gpu: <GPU数量>
```

---

### 第四步：业务调度策略 (Pod 配置)

后续所有的 GPU 任务，**必须**在 YAML 中包含以下双重限制：

```
apiVersion: v1
kind: Pod
metadata:
  name: gpu-workload
  labels:
    app: gpu-training
spec:
  # ============================================
  # 强制绑定 GPU 节点（导航员）
  # ============================================
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: gpu
            operator: In
            values: ["true"]
  
  # ============================================
  # 容忍 GPU 节点的污点，允许 Pod 运行（通行证）
  # ============================================
  tolerations:
  - key: "gpu-node"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
  
  # ============================================
  # 容器配置
  # ============================================
  containers:
  - name: gpu-container
    image: nvidia/cuda:12.2.0-base-ubuntu22.04
    command: ["nvidia-smi"]
    
    # ============================================
    # 申请 GPU 资源（必须指定）
    # ============================================
    resources:
      limits:
        nvidia.com/gpu: 1  # 申请 1 块 GPU
      requests:
        nvidia.com/gpu: 1
  
  # ============================================
  # 重启策略
  # ============================================
  restartPolicy: Never
```

#### 关键配置说明

| 配置项 | 作用 | 是否必需 |
|--------|------|----------|
| `affinity.nodeAffinity` | 强制调度到 GPU 节点 | ✅ 必需 |
| `tolerations` | 容忍 GPU 节点污点 | ✅ 必需 |
| `resources.limits.nvidia.com/gpu` | 申请 GPU 资源 | ✅ 必需 |
| `resources.requests.nvidia.com/gpu` | 预留 GPU 资源 | ✅ 建议 |

---

### 第五步：验证调度效果

#### 测试 1：普通 Pod 不应调度到 GPU 节点

```
apiVersion: v1
kind: Pod
metadata:
  name: test-no-gpu
spec:
  containers:
  - name: nginx
    image: nginx:latest
  restartPolicy: Never
```

```bash
kubectl apply -f test-no-gpu.yaml
kubectl get pod test-no-gpu -o wide
# 预期：调度到 k8s-worker-1/2/3，而不是 k8s-gpu-worker-1
```

#### 测试 2：GPU Pod 应调度到 GPU 节点

```
kubectl apply -f gpu-workload.yaml
kubectl get pod gpu-workload -o wide
# 预期：调度到 k8s-gpu-worker-1

kubectl logs gpu-workload
# 预期：看到 nvidia-smi 输出
```

---

## 4. 运维检查清单 (Checklist)

### 📊 日常检查命令

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| **污点状态** | `kubectl get nodes k8s-gpu-worker-1 -o jsonpath='{.spec.taints}'` | `gpu-node=true:NoSchedule` |
| **标签状态** | `kubectl get nodes k8s-gpu-worker-1 --show-labels` | 包含 `gpu=true` |
| **节点状态** | `kubectl get nodes k8s-gpu-worker-1` | `Ready` |
| **GPU 资源** | `kubectl describe node k8s-gpu-worker-1 \| grep -A 5 "Allocatable:"` | `nvidia.com/gpu: <数量>` |
| **插件就绪** | `kubectl get ds -n nvidia-device-plugin` | DaemonSet 处于 `Ready` 状态 |
| **GPU Pod 分布** | `kubectl get pods -o wide \| grep gpu` | 全部在 GPU 节点 |
| **普通 Pod 分布** | `kubectl get pods -o wide \| grep -v gpu` | 不在 GPU 节点 |

### 🔍 一键检查脚本

```
#!/bin/bash
# gpu-node-health-check.sh

NODE="k8s-gpu-worker-1"

echo "=== GPU 节点健康检查 ==="
echo ""

# 1. 节点状态
echo "1️⃣  节点状态:"
kubectl get nodes $NODE
echo ""

# 2. 污点检查
echo "2️⃣  污点配置:"
TAINTS=$(kubectl get nodes $NODE -o jsonpath='{.spec.taints}')
if [[ "$TAINTS" == *"gpu-node"* ]]; then
    echo "✅ 污点已配置: $TAINTS"
else
    echo "❌ 污点未配置!"
fi
echo ""

# 3. 标签检查
echo "3️⃣  标签配置:"
LABELS=$(kubectl get nodes $NODE --show-labels | grep -o 'gpu=[^,]*')
if [[ "$LABELS" == "gpu=true" ]]; then
    echo "✅ 标签已配置: $LABELS"
else
    echo "❌ 标签未配置!"
fi
echo ""

# 4. GPU 资源
echo "4️⃣  GPU 资源:"
kubectl describe node $NODE | grep -A 3 "nvidia.com/gpu"
echo ""

# 5. Device Plugin
echo "5️⃣  Device Plugin 状态:"
kubectl get ds -n nvidia-device-plugin
echo ""

# 6. 调度验证
echo "6️⃣  GPU Pod 分布:"
GPU_PODS=$(kubectl get pods -o wide --all-namespaces | grep -E "Running.*$NODE" | wc -l)
echo "   GPU 节点上运行的 Pod 数量: $GPU_PODS"
echo ""

echo "=== 检查完成 ==="
```

---

## 5. 故障排查

### ❌ 问题 1：Pod 无法调度到 GPU 节点

**症状**：
```
Warning  FailedScheduling  pod/gpu-workload  0/4 nodes are available: 
  1 node(s) had untolerated taint {gpu-node: true}, 
  3 node(s) didn't match Pod's node affinity/selector.
```

**原因分析**：
1. Pod 缺少 `tolerations` 配置
2. Pod 缺少 `nodeAffinity` 配置
3. 污点或标签配置错误

**解决方案**：
```bash
# 检查 Pod 配置
kubectl get pod gpu-workload -o yaml | grep -A 10 "tolerations"
kubectl get pod gpu-workload -o yaml | grep -A 10 "affinity"

# 检查节点配置
kubectl describe node k8s-gpu-worker-1 | grep -E "Taints|Labels"
```

---

### ❌ 问题 2：GPU 资源不可用

**症状**：
```
Warning  FailedCreatePodSandBox  pod/gpu-workload  
  rpc error: code = Unknown desc = failed to create containerd task: 
  no nvidia runtime configured
```

**原因分析**：
1. NVIDIA Container Toolkit 未正确安装
2. containerd 未配置 NVIDIA runtime
3. NVIDIA Device Plugin 未运行

**解决方案**：
```bash
# 1. 检查 NVIDIA Container Toolkit
ssh k8s-gpu-worker-1 "nvidia-container-cli info"

# 2. 检查 containerd 配置
ssh k8s-gpu-worker-1 "grep -A 5 'nvidia-container-runtime' /etc/containerd/config.toml"

# 3. 重启 containerd
ssh k8s-gpu-worker-1 "sudo systemctl restart containerd"

# 4. 检查 Device Plugin
kubectl get pods -n nvidia-device-plugin
kubectl logs -n nvidia-device-plugin <device-plugin-pod-name>
```

---

### ❌ 问题 3：节点一直处于 NotReady 状态

**症状**：
```
NAME               STATUS     ROLES    AGE   VERSION
k8s-gpu-worker-1   NotReady   <none>   10m   v1.34.8
```

**原因分析**：
1. kubelet 未启动
2. 网络插件未就绪
3. 内核参数未正确配置

**解决方案**：
```bash
# 1. 检查 kubelet 状态
ssh k8s-gpu-worker-1 "sudo systemctl status kubelet"
ssh k8s-gpu-worker-1 "sudo journalctl -u kubelet -f"

# 2. 检查内核参数
ssh k8s-gpu-worker-1 "cat /proc/sys/net/ipv4/ip_forward"
# 应为 1

# 3. 重新应用 sysctl
ssh k8s-gpu-worker-1 "sudo sysctl --system"

# 4. 重启 kubelet
ssh k8s-gpu-worker-1 "sudo systemctl restart kubelet"
```

---

### ❌ 问题 4：普通 Pod 被调度到 GPU 节点

**症状**：
```
NAME               READY   STATUS    NODE
test-app           1/1     Running   k8s-gpu-worker-1  # ❌ 不应该在这里
```

**原因分析**：
1. 污点未正确配置
2. 污点 Effect 使用了 `PreferNoSchedule` 而非 `NoSchedule`

**解决方案**：
```bash
# 1. 检查污点
kubectl get nodes k8s-gpu-worker-1 -o jsonpath='{.spec.taints}'

# 2. 重新配置污点
kubectl taint nodes k8s-gpu-worker-1 gpu-node=true:NoSchedule --overwrite

# 3. 驱逐已调度的普通 Pod
kubectl delete pod test-app --grace-period=30
```

---

## 6. 最佳实践

### ✅ 推荐做法

#### 1. 命名规范

```yaml
# 污点键名：使用描述性名称
gpu-node: "true"          # ✅ 好
gpu: "true"               # ❌ 不够明确

# 标签键名：遵循 Kubernetes 约定
app.kubernetes.io/gpu: "true"  # ✅ 标准格式
gpu: "true"                      # ✅ 简洁格式
```

#### 2. 多 GPU 资源管理

```yaml
# 申请特定数量的 GPU
resources:
  limits:
    nvidia.com/gpu: 2  # 申请 2 块 GPU

# 使用 MIG (Multi-Instance GPU) 时
resources:
  limits:
    nvidia.com/mig-1g.5gb: 1  # 申请 1 个 MIG 实例
```

#### 3. 优先级与抢占

```yaml
# 为 GPU 任务设置高优先级
spec:
  priorityClassName: high-priority
  preemptionPolicy: PreemptLowerPriority
```

创建 PriorityClass：
```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: high-priority
value: 1000000
globalDefault: false
description: "High priority for GPU workloads"
```

#### 4. 资源配额限制

```yaml
# 在 namespace 级别限制 GPU 使用
apiVersion: v1
kind: ResourceQuota
metadata:
  name: gpu-quota
  namespace: gpu-workloads
spec:
  hard:
    requests.nvidia.com/gpu: 4  # 最多申请 4 块 GPU
    limits.nvidia.com/gpu: 4
```

#### 5. 监控与告警

```bash
# 安装 Prometheus + Grafana 监控 GPU
helm install prometheus-stack prometheus-community/kube-prometheus-stack

# 监控指标
# - node_gpu_utilization
# - pod_gpu_usage
# - node_gpu_memory_used_bytes
```

---

### ⚠️ 注意事项

1. **不要在 GPU 节点运行普通业务**
   - GPU 节点资源宝贵，应专用于 GPU 任务
   - 使用 Taint 严格隔离

2. **定期更新 NVIDIA 驱动和工具包**
   ```bash
   # 检查驱动版本
   nvidia-smi
   
   # 检查 Container Toolkit 版本
   dpkg -l | grep nvidia-container-toolkit
   ```

3. **备份节点配置**
   ```bash
   # 导出节点配置
   kubectl get node k8s-gpu-worker-1 -o yaml > gpu-node-backup.yaml
   ```

4. **测试变更前的影响**
   - 在 staging 环境先验证
   - 使用 `kubectl diff` 预览变更

5. **文档化所有自定义配置**
   - 记录污点、标签的含义
   - 维护 GPU 任务的标准模板

---

## 📚 相关文档

- [Kubernetes Taints and Tolerations](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)
- [Node Affinity](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#node-affinity)
- [NVIDIA Device Plugin](https://github.com/NVIDIA/k8s-device-plugin)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/index.html)

---

## 🔄 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-05-20 | v1.0 | 初始版本，包含完整的 GPU 节点接入与隔离指南 |

---

**维护者**: Infrastructure Team  
**最后更新**: 2026-05-20
