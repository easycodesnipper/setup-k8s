# NVIDIA Container Toolkit Integration Guide

## Quick Start

To enable NVIDIA GPU support in your Kubernetes cluster, follow these steps:

### 1. Enable the Role in group_vars

Edit `group_vars/all/all.yml` and add:

```yaml
# Enable NVIDIA Container Toolkit installation
nvidia_container_toolkit_enabled: true

# Optional: Specify a specific version
# nvidia_container_toolkit_version: "1.13.5-1"
```

### 2. Add Role to Playbook

Update `playbook-install.yml` to include the NVIDIA role after containerd:

```yaml
- name: Prepare Kubernetes cluster
  hosts: k8s_cluster
  become: true
  any_errors_fatal: true
  pre_tasks:
    - name: Test network reachability
      ansible.builtin.ping:
      tags: always
  roles:
    - role: prerequisite
      tags: prereq
    - role: containerd
      tags: containerd
    - role: nvidia-container-toolkit
      tags: nvidia-gpu
      when: nvidia_container_toolkit_enabled | default(false) | bool
    - role: kubernetes
      tags: kubernetes
  tags: prepare
```

### 3. Run the Playbook

```bash
# Install with NVIDIA GPU support
ansible-playbook -i inventory.ini playbook-install.yml --tags "prereq,containerd,nvidia-gpu,kubernetes"

# Or run the full installation
ansible-playbook -i inventory.ini playbook-install.yml
```

### 4. Verify Installation

After installation, verify on GPU nodes:

```bash
# Check if nvidia-container-runtime is installed
which nvidia-container-runtime

# Test NVIDIA runtime
sudo ctr run --runtime io.containerd.runc.v2 --rm docker.io/nvidia/cuda:11.0-base nvidia-test nvidia-smi

# Verify containerd configuration
grep -A 5 "nvidia" /etc/containerd/config.toml
```

## Advanced Configuration

### Target Specific Nodes

If you have mixed GPU and non-GPU nodes, use host variables:

**inventory.ini:**
```ini
[gpu_nodes]
gpu-node-1 ansible_host=192.168.1.10
gpu-node-2 ansible_host=192.168.1.11

[worker_nodes]
worker-node-1 ansible_host=192.168.1.20
worker-node-2 ansible_host=192.168.1.21

[k8s_cluster:children]
gpu_nodes
worker_nodes
```

**group_vars/gpu_nodes.yml:**
```yaml
nvidia_container_toolkit_enabled: true
```

### Custom Repository URL

If you need to use a mirror or private repository:

```yaml
nvidia_docker_repo_url: "https://your-mirror.example.com/libnvidia-container"
```

### Skip containerd Restart

If you want to manually control when containerd restarts:

```yaml
nvidia_container_toolkit_restart_containerd: false
```

## Kubernetes GPU Usage

After installation, you can schedule GPU workloads:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-example
spec:
  runtimeClassName: nvidia
  containers:
  - name: cuda-vector-add
    image: "nvidia/samples:vectoradd-cuda11.2.1"
    resources:
      limits:
        nvidia.com/gpu: 1
```

## Troubleshooting

### Issue: NVIDIA drivers not found

**Solution:** Ensure NVIDIA drivers are installed before running this role:
```bash
nvidia-smi
```

### Issue: containerd not configured

**Solution:** Make sure the containerd role runs before nvidia-container-toolkit:
```yaml
roles:
  - containerd
  - nvidia-container-toolkit
```

### Issue: Runtime class not available in Kubernetes

**Solution:** You may need to install the NVIDIA Device Plugin:
```bash
kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.1/deployments/static/nvidia-device-plugin.yml
```

## Tags

Use Ansible tags for selective execution:

```bash
# Only install NVIDIA Container Toolkit
ansible-playbook -i inventory.ini playbook-install.yml --tags "nvidia-gpu"

# Skip NVIDIA installation
ansible-playbook -i inventory.ini playbook-install.yml --skip-tags "nvidia-gpu"
```

## Best Practices

### Mixed GPU and Non-GPU Clusters

The role is designed to work seamlessly in mixed clusters:

**GPU Detection Behavior:**
- ✅ **Non-blocking**: Installation proceeds on all enabled nodes
- ℹ️ **Informative**: Shows GPU status for each node
- 📋 **Advisory**: Warns if GPU not detected but doesn't fail

**Option 1: Enable Only on GPU Nodes (Recommended)**

```ini
# inventory.ini
[gpu_nodes]
gpu-node-1 ansible_host=192.168.1.10
gpu-node-2 ansible_host=192.168.1.11

[worker_nodes]
worker-node-1 ansible_host=192.168.1.20
worker-node-2 ansible_host=192.168.1.21
```

```yaml
# group_vars/gpu_nodes.yml
nvidia_container_toolkit_enabled: true

# group_vars/worker_nodes.yml
nvidia_container_toolkit_enabled: false  # Skip on non-GPU nodes
```

**Option 2: Enable on All Nodes with Warnings**

```yaml
# group_vars/all/all.yml
nvidia_container_toolkit_enabled: true
```

This will:
- Install on all nodes
- Show GPU detection status for each node
- Display warnings on non-GPU nodes
- Continue playbook execution without interruption

Useful for:
- Pre-provisioning clusters
- Testing environments
- Future-proofing (adding GPUs later)
