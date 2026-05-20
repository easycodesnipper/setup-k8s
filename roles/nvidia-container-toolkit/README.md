# NVIDIA Container Toolkit Role

This Ansible role installs and configures the NVIDIA Container Toolkit to enable GPU support in containers managed by containerd.

## Requirements

- NVIDIA GPU drivers must be installed on the host system
- containerd must be installed and configured
- Supported operating systems:
  - Ubuntu (18.04, 20.04, 22.04)
  - Debian (10, 11, 12)
  - RHEL/CentOS/Rocky Linux/AlmaLinux (7, 8, 9)

## Role Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `nvidia_container_toolkit_enabled` | `false` | Enable or disable NVIDIA Container Toolkit installation |
| `nvidia_container_toolkit_version` | `""` | Specific version to install (empty for latest) |
| `nvidia_container_toolkit_configure_containerd` | `true` | Configure containerd to use NVIDIA runtime |
| `nvidia_container_toolkit_restart_containerd` | `true` | Restart containerd after configuration |
| `nvidia_docker_repo_url` | `"https://nvidia.github.io/libnvidia-container"` | Base URL for NVIDIA Docker repository |

### GPU Detection

The role automatically detects NVIDIA GPU presence and provides informative feedback:

**Detection Methods:**
1. `nvidia-smi` command (checks if drivers are loaded)
2. `lspci` (checks for NVIDIA hardware)

**Behavior:**
- ✅ **Non-blocking**: Playbook continues regardless of GPU detection result
- ℹ️ **Informative**: Shows clear status messages about GPU presence
- ⚠️ **Advisory**: Warns if GPU not found but still proceeds with installation

This allows flexible deployment scenarios like pre-provisioning or mixed clusters.

## Dependencies

This role should be run after:
- `containerd` role (to ensure containerd is installed)
- NVIDIA GPU drivers are installed on the host

## Safety Features

### Non-Destructive Configuration

This role safely adds NVIDIA runtime configuration to your existing containerd configuration:

- ✅ **Preserves existing configurations**: Only appends NVIDIA runtime settings without modifying other configurations
- ✅ **Automatic backup**: Creates timestamped backups before making any changes
- ✅ **Idempotent**: Safe to run multiple times; won't duplicate configurations
- ✅ **Verification**: Validates that configuration was added successfully

### Backup Location

Backups are saved as: `/etc/containerd/config.toml.bak.nvidia.<timestamp>`

## Example Playbook

```yaml
- hosts: gpu_nodes
  become: true
  roles:
    - role: containerd
    - role: nvidia-container-toolkit
      vars:
        nvidia_container_toolkit_enabled: true
```

## Usage in Main Playbook

Add the role to your playbook after the containerd role:

```yaml
- name: Prepare Kubernetes cluster with GPU support
  hosts: k8s_cluster
  become: true
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
```

## Configuration

After installation, you can use NVIDIA GPUs in your Kubernetes pods by specifying the runtime class:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod
spec:
  runtimeClassName: nvidia
  containers:
    - name: cuda-container
      image: nvidia/cuda:11.0-base
      resources:
        limits:
          nvidia.com/gpu: 1
```

## Verification

To verify the installation:

```bash
# Check if nvidia-container-runtime is available
which nvidia-container-runtime

# Check if NVIDIA runtime is configured in containerd
grep -A 3 "nvidia" /etc/containerd/config.toml

# Test with containerd
ctr run --runtime io.containerd.runc.v2 --rm docker.io/nvidia/cuda:11.0-base nvidia-test nvidia-smi
```

## Troubleshooting

### Restore from Backup

If you need to restore the original configuration:

```bash
# List available backups
ls -la /etc/containerd/config.toml.bak.nvidia.*

# Restore a specific backup
cp /etc/containerd/config.toml.bak.nvidia.<timestamp> /etc/containerd/config.toml

# Restart containerd
systemctl restart containerd
```

## License

MIT

## Author

Infrastructure Team
