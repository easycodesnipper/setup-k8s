# NVIDIA Device Plugin Complete Installation Workflow

## 📊 Automated Execution Flow

When you run `playbook-plugins.yml` with `nvidia-device-plugin` enabled, the system automatically executes in the following order:

```
┌─────────────────────────────────────────────────────────────┐
│  ansible-playbook playbook-plugins.yml                      │
│    -e "k8s_plugins_only=nvidia-device-plugin"               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Install NVIDIA GPU Driver                          │
│  Role: nvidia-driver                                        │
│  Target: All nodes in [gpu-workers] group                   │
│                                                             │
│  Tasks:                                                     │
│  • Detect GPU hardware (lspci)                             │
│  • Check if driver already installed (nvidia-smi)          │
│  • Install via ubuntu-drivers autoinstall                  │
│  • Verify installation                                      │
│  • Optional: Reboot system                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Install NVIDIA Container Toolkit                   │
│  Role: nvidia-container-toolkit                             │
│  Target: All nodes in [gpu-workers] group                   │
│                                                             │
│  Tasks:                                                     │
│  • Add NVIDIA repository                                    │
│  • Install packages (toolkit, base, libs)                  │
│  • Configure containerd runtime                             │
│  • Restart containerd                                       │
│  • Verify nvidia runtime available                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Deploy NVIDIA Device Plugin (Helm Chart)           │
│  Task: _install_plugin.yml                                  │
│  Target: k8s-controller-1 (runs helm commands)              │
│                                                             │
│  Tasks:                                                     │
│  • Add Helm repository                                      │
│  • Pull chart to local directory                            │
│  • Render values from template                              │
│  • helm upgrade --install                                   │
│  • Wait for DaemonSet Ready                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  ✅ Complete! GPU resources exposed to Kubernetes           │
│                                                             │
│  Verification:                                              │
│  • kubectl get pods -n nvidia-device-plugin                 │
│  • kubectl describe node k8s-gpu-worker-1 | grep gpu       │
│  • Deploy GPU workload with tolerations & affinity         │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

Ensure the `gpu-workers` group is defined in `inventory.ini`:

```ini
[gpu-workers]
k8s-gpu-worker-1 ansible_host=10.17.3.30 ansible_user=user
```

### One-Click Installation (Recommended)

```bash
cd /home/dylan/workspace/infrastructure/setup-k8s

# Execute complete installation workflow
ansible-playbook -i inventory.ini playbook-plugins.yml \
  -e "k8s_plugins_only=nvidia-device-plugin"
```

**Expected Output**:
```
TASK [Install NVIDIA GPU Driver on all GPU nodes] ************
changed: [k8s-controller-1] => (item=Install NVIDIA driver on k8s-gpu-worker-1)

TASK [Install NVIDIA Container Toolkit on all GPU nodes] *****
changed: [k8s-controller-1] => (item=Install NVIDIA Container Toolkit on k8s-gpu-worker-1)

TASK [Plugin nvidia-device-plugin | Install/Upgrade Helm release] ***
changed: [k8s-controller-1]

TASK [Plugin nvidia-device-plugin | Wait for Resource Ready] ***
ok: [k8s-controller-1]
```

## 🔍 Step-by-Step Verification

### Verify Step 1: NVIDIA Driver

```bash
# SSH to GPU node
ssh user@k8s-gpu-worker-1

# Check driver status
nvidia-smi

# Expected output example:
# +-----------------------------------------------------------------------------+
# | NVIDIA-SMI 550.54.14    Driver Version: 550.54.14    CUDA Version: 12.4     |
# |-------------------------------+----------------------+----------------------+
# | GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
# | Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
# |===============================+======================+======================|
# |   0  RTX 4000 Ada ...    Off  | 00000000:00:08.0 Off |                  Off |
# +-------------------------------+----------------------+----------------------+
```

### Verify Step 2: Container Toolkit

```bash
# Execute on GPU node
ssh user@k8s-gpu-worker-1

# Check containerd configuration
sudo containerd config dump | grep -A 10 "\[plugins.\"io.containerd.grpc.v1.cri\".containerd.runtimes.nvidia\]"

# Expected to see nvidia runtime configuration
```

### Verify Step 3: Device Plugin

```bash
# Execute on controller node
kubectl get pods -n nvidia-device-plugin

# Expected output:
# NAME                              READY   STATUS    RESTARTS   AGE
# nvdp-nvidia-device-plugin-xxxxx   1/1     Running   0          2m

# Check GPU resources
kubectl describe node k8s-gpu-worker-1 | grep -A 10 "Allocatable:"

# Expected to see:
# Allocatable:
#   cpu:                6
#   ephemeral-storage:  73878040045
#   hugepages-1Gi:      0
#   hugepages-2Mi:      0
#   memory:             16266924Ki
#   nvidia.com/gpu:     1  ← GPU resources exposed
```

## 🧪 Test GPU Scheduling

Create a test Pod to verify GPU scheduling:

```yaml
# test-gpu-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-test
spec:
  # Node Affinity - Force scheduling to GPU nodes
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: gpu
            operator: In
            values: ["true"]
  
  # Tolerations - Tolerate GPU node taints
  tolerations:
  - key: "gpu-node"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
  
  containers:
  - name: cuda-container
    image: nvidia/cuda:12.2.0-base-ubuntu22.04
    command: ["nvidia-smi"]
    
    # GPU resource requests
    resources:
      limits:
        nvidia.com/gpu: 1
      requests:
        nvidia.com/gpu: 1
  
  restartPolicy: Never
```

```bash
# Deploy test Pod
kubectl apply -f test-gpu-pod.yaml

# Check Pod status
kubectl get pods gpu-test -o wide

# Expected: Pod should run on k8s-gpu-worker-1

# Check logs to confirm GPU availability
kubectl logs gpu-test

# Expected output: Full nvidia-smi output
```

## ⚙️ Advanced Configuration

### Skip Pre-installation Steps

If you have manually installed the driver and toolkit, you can skip the first two steps:

```bash
ansible-playbook -i inventory.ini playbook-plugins.yml \
  -e "k8s_plugins_only=nvidia-device-plugin" \
  --skip-tags "plugin-nvidia-device-plugin-preinstall"
```

### Custom Driver Version

```yaml
# group_vars/gpu-workers.yml
nvidia_driver_install_method: "specific_version"
nvidia_driver_version: "550"
nvidia_driver_reboot: true
```

### Disable Automatic Reboot

```yaml
# group_vars/gpu-workers.yml
nvidia_driver_reboot: false
```

## 🐛 Troubleshooting

### Issue 1: Driver Installation Failed

```bash
# View detailed errors
ansible-playbook -i inventory.ini playbook-plugins.yml \
  -e "k8s_plugins_only=nvidia-device-plugin" -vvv

# Manual check
ssh user@k8s-gpu-worker-1 "cat /var/log/apt/term.log | tail -50"
```

### Issue 2: Container Toolkit Configuration Failed

```bash
# Check containerd status
ssh user@k8s-gpu-worker-1 "systemctl status containerd"

# Check nvidia runtime
ssh user@k8s-gpu-worker-1 "sudo ctr plugins ls | grep nvidia"
```

### Issue 3: Device Plugin Pod Not Ready

```bash
# Check Pod events
kubectl describe pod -n nvidia-device-plugin -l app.kubernetes.io/name=nvidia-device-plugin

# Check logs
kubectl logs -n nvidia-device-plugin -l app.kubernetes.io/name=nvidia-device-plugin
```

## 📝 Key Points

1. **Execution order matters**: Driver → Toolkit → Device Plugin
2. **Idempotent design**: Repeated execution won't break existing configurations
3. **Automatic detection**: Skips installation if driver is already installed
4. **Tag-based management**: Use tags to control execution granularity
5. **Fault tolerance**: Single node failure won't interrupt the entire process

## 🎯 Next Steps

After completing NDP installation, you can:

1. **Deploy GPU workloads** (e.g., SOM API Service)
2. **Monitor GPU usage** (via Prometheus + Grafana)
3. **Configure GPU sharing** (MIG or Time-Slicing)
4. **Set up autoscaling** (HPA based on GPU metrics)
