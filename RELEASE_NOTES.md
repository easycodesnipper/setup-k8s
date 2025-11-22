# Release Notes

## v1.0.0

**Release Date:** 2025-11-22

### Features

- **Automated Kubernetes Cluster Setup**:
  - Sets up system prerequisites (swap, kernel modules).
  - Installs containerd runtime.
  - Installs Kubernetes components (kubeadm, kubelet, kubectl).
  - Initializes the control plane.
  - Joins worker nodes to the cluster.

- **Plugin Support**:
  - **Metrics Server**: For cluster resource metrics.
  - **Kubernetes Dashboard**: Web-based UI for cluster management.
  - **MetalLB**: LoadBalancer implementation for bare metal clusters.
  - **Local Path Provisioner**: Dynamic provisioning of local storage.

- **Cluster Management**:
  - **Reset**: Automated cluster reset and cleanup.
  - **Verify**: Cluster status verification.

### Usage

Refer to [README](./README.md) for detailed installation and configuration instructions.
