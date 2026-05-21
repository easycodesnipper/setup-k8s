# NVIDIA GPU Driver Installation Role

This Ansible role installs NVIDIA GPU drivers on Ubuntu/Debian systems, specifically designed for Kubernetes GPU worker nodes with VFIO GPU passthrough.

## Requirements

- Ubuntu 18.04/20.04/22.04/24.04 or Debian 10/11/12
- NVIDIA GPU hardware present (physical or via VFIO passthrough)
- Root/sudo access
- Internet access to download drivers

## Role Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `nvidia_driver_enabled` | `{{ nct_enabled }}` | Enable/disable driver installation |
| `nvidia_driver_install_method` | `autoinstall` | Installation method: `autoinstall` or `specific_version` |
| `nvidia_driver_version` | `""` | Specific driver version (e.g., `535`, `550`) |
| `nvidia_driver_reboot` | `true` | Reboot after installation |
| `nvidia_driver_reboot_timeout` | `300` | Timeout for reboot wait (seconds) |
| `nvidia_driver_dkms` | `true` | Enable DKMS for kernel module rebuild |

## Usage Examples

### Example 1: Auto-install recommended driver (Recommended)

```yaml
# inventory.ini
[gpu-workers]
k8s-gpu-worker-1 ansible_host=10.17.3.30

# playbook.yml
- hosts: gpu-workers
  roles:
    - role: nvidia-driver
      vars:
        nct_enabled: true
        nvidia_driver_install_method: autoinstall
        nvidia_driver_reboot: true
```

### Example 2: Install specific driver version

```yaml
- hosts: gpu-workers
  roles:
    - role: nvidia-driver
      vars:
        nct_enabled: true
        nvidia_driver_install_method: specific_version
        nvidia_driver_version: "550"
        nvidia_driver_reboot: true
```

### Example 3: Integration with nvidia-container-toolkit

```yaml
# Install both driver and container toolkit in sequence
- hosts: gpu-workers
  tasks:
    - name: Install NVIDIA GPU driver
      ansible.builtin.include_role:
        name: nvidia-driver
      vars:
        node_item: "{{ inventory_hostname }}"
        nct_enabled: true
    
    - name: Install NVIDIA Container Toolkit
      ansible.builtin.include_role:
        name: nvidia-container-toolkit
      vars:
        nct_enabled: true
```

## Installation Methods

### Method 1: autoinstall (Recommended)

Uses `ubuntu-drivers autoinstall` to automatically detect and install the best driver for your GPU.

**Pros:**
- ✅ Automatic hardware detection
- ✅ Installs optimal driver version
- ✅ Handles dependencies automatically

**Cons:**
- ⚠️ Less control over exact version

### Method 2: specific_version

Installs a specific driver version using apt package manager.

**Pros:**
- ✅ Exact version control
- ✅ Predictable deployments

**Cons:**
- ⚠️ Must verify compatibility manually
- ⚠️ May fail if version not available

## VFIO GPU Passthrough Notes

For VMs with VFIO GPU passthrough:

1. **Host Configuration**: Ensure VFIO is properly configured on the physical host
2. **VM Detection**: The role will detect GPU via `lspci` inside the VM
3. **Driver Installation**: Install drivers inside the VM (not on the host)
4. **Verification**: Use `nvidia-smi` inside the VM to confirm

## Verification

After installation, verify the driver is working:

```bash
# Check driver status
nvidia-smi

# Expected output:
# +-----------------------------------------------------------------------------+
# | NVIDIA-SMI 550.54.14    Driver Version: 550.54.14    CUDA Version: 12.4     |
# |-------------------------------+----------------------+----------------------+
# | GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
# | Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
# |===============================+======================+======================|
# |   0  RTX 4000 Ada ...    Off  | 00000000:00:08.0 Off |                  Off |
# +-------------------------------+----------------------+----------------------+
```

## Troubleshooting

### Issue: No GPU detected

```bash
# Check if GPU is visible
lspci | grep -i nvidia

# If not visible, check:
# 1. VFIO configuration on host
# 2. VM BIOS/UEFI settings
# 3. IOMMU enabled in kernel parameters
```

### Issue: Driver installation fails

```bash
# Check logs
cat /var/log/apt/term.log

# Common solutions:
# 1. Update system: sudo apt update && sudo apt upgrade
# 2. Remove conflicting packages: sudo apt purge nvidia-*
# 3. Retry installation
```

### Issue: nvidia-smi not found after reboot

```bash
# Check if module is loaded
lsmod | grep nvidia

# Check dmesg for errors
dmesg | grep -i nvidia

# Verify package installation
dpkg -l | grep nvidia-driver
```

## Dependencies

This role should be run **before** `nvidia-container-toolkit` role:

```
Installation Order:
1. nvidia-driver (this role)
2. nvidia-container-toolkit
3. Kubernetes join (for GPU workers)
4. nvidia-device-plugin (Kubernetes plugin)
```

## Safety Features

- ✅ Non-destructive: Skips if driver already installed
- ✅ Hardware detection: Only installs if GPU is present
- ✅ Reboot management: Optional automatic reboot with health check
- ✅ Retry logic: Handles transient network failures
- ✅ Verification: Confirms installation success before proceeding
