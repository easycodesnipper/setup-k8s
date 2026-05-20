# Join New Nodes to Kubernetes Cluster

This playbook allows you to add new worker nodes to an existing Kubernetes cluster without disrupting the current setup.

## Prerequisites

- ✅ Kubernetes cluster must be already initialized (via `playbook-install.yml`)
- ✅ Controller nodes must be accessible and healthy
- ✅ New nodes must have network connectivity to the cluster

## Usage

### Basic Usage

```bash
# Add nodes defined in [new_workers] group
ansible-playbook -i inventory.ini playbook-join.yml
```

### Specify Target Hosts

```bash
# Join specific hosts or groups
ansible-playbook -i inventory.ini playbook-join.yml \
  --extra-vars "target_hosts=my-new-workers"

# Join a single node
ansible-playbook -i inventory.ini playbook-join.yml \
  --extra-vars "target_hosts=new-node-1"
```

### Using Tags

```bash
# Only prepare nodes (don't join yet)
ansible-playbook -i inventory.ini playbook-join.yml --tags "prepare"

# Only join nodes (skip preparation)
ansible-playbook -i inventory.ini playbook-join.yml --tags "join"

# Skip NVIDIA Container Toolkit installation
ansible-playbook -i inventory.ini playbook-join.yml --skip-tags "nct"
```

## Inventory Setup

### Option 1: Define New Nodes Group

Add a new group to your `inventory.ini`:

```ini
[new_workers]
new-worker-1 ansible_host=10.17.3.40 ansible_user=user
new-worker-2 ansible_host=10.17.3.41 ansible_user=user

[k8s_cluster:children]
controllers
workers
gpu-workers
new_workers
```

### Option 2: Add to Existing Groups

Move nodes from `[new_workers]` to `[workers]` or `[gpu-workers]` after joining:

```ini
[workers]
k8s-worker-1 ansible_host=10.17.3.20 ansible_user=user
k8s-worker-2 ansible_host=10.17.3.21 ansible_user=user
# New nodes added here
new-worker-1 ansible_host=10.17.3.40 ansible_user=user
```

### Option 3: GPU Workers

For GPU-enabled nodes:

```ini
[gpu-workers]
k8s-gpu-worker-1 ansible_host=10.17.3.30 ansible_user=user
# New GPU node
new-gpu-worker-1 ansible_host=10.17.3.50 ansible_user=user
```

Enable NVIDIA Container Toolkit:

```yaml
# group_vars/gpu-workers.yml
nvidia_container_toolkit_enabled: true
```

## Examples

### Example 1: Add Single Worker Node

**Step 1:** Update inventory
```ini
[new_workers]
new-worker-1 ansible_host=10.17.3.40 ansible_user=user
```

**Step 2:** Run playbook
```bash
ansible-playbook -i inventory.ini playbook-join.yml \
  --extra-vars "target_hosts=new_workers"
```

**Step 3:** Verify
```bash
kubectl get nodes
```

### Example 2: Add Multiple GPU Nodes

**Step 1:** Update inventory
```ini
[new_gpu_workers]
gpu-worker-2 ansible_host=10.17.3.51 ansible_user=user
gpu-worker-3 ansible_host=10.17.3.52 ansible_user=user
```

**Step 2:** Create group vars
```yaml
# group_vars/new_gpu_workers.yml
nvidia_container_toolkit_enabled: true
```

**Step 3:** Run playbook
```bash
ansible-playbook -i inventory.ini playbook-join.yml \
  --extra-vars "target_hosts=new_gpu_workers"
```

### Example 3: Prepare Nodes Only

If you want to prepare nodes first and join later:

```bash
# Step 1: Prepare nodes
ansible-playbook -i inventory.ini playbook-join.yml \
  --extra-vars "target_hosts=new_workers" \
  --tags "prepare"

# Step 2: Join nodes (when ready)
ansible-playbook -i inventory.ini playbook-join.yml \
  --extra-vars "target_hosts=new_workers" \
  --tags "join"
```

## What This Playbook Does

### 1. Validate Cluster
- Checks if cluster is initialized and accessible
- Verifies controller node availability

### 2. Prepare New Nodes
Installs and configures on each new node:
- **Prerequisites**: Kernel modules, sysctl settings, swap disabled
- **Containerd**: Container runtime installation and configuration
- **NVIDIA Container Toolkit** (optional): GPU support for containerd
- **Kubernetes Components**: kubelet, kubeadm, kubectl

### 3. Join Cluster
- Generates join command from controller
- Executes join command on new nodes
- Adds nodes to the cluster

### 4. Verification
- Waits for nodes to become Ready
- Displays cluster node status
- Warns if nodes are not ready yet

## Troubleshooting

### Issue: Cluster Not Initialized

**Error:**
```
Kubernetes cluster is not initialized or not accessible.
```

**Solution:**
Run the initial installation playbook first:
```bash
ansible-playbook -i inventory.ini playbook-install.yml
```

### Issue: Node Not Becoming Ready

**Check node status:**
```bash
kubectl get nodes
kubectl describe node <node-name>
```

**Common causes:**
- CNI plugin not installed on controller
- Network connectivity issues
- Firewall blocking ports

**Check logs:**
```bash
# On the new node
journalctl -u kubelet -f

# On controller
kubectl logs -n kube-system -l k8s-app=kube-proxy
```

### Issue: NVIDIA GPU Not Detected

The role will show a warning but continue installation. To enable GPU support:

1. Install NVIDIA drivers on the node
2. Reboot the node
3. Re-run the playbook with `nvidia_container_toolkit_enabled: true`

### Issue: Duplicate Node Names

If a node was previously part of the cluster:

```bash
# On the controller
kubectl delete node <node-name>

# On the node
kubeadm reset -f
systemctl restart kubelet

# Re-run the join playbook
ansible-playbook -i inventory.ini playbook-join.yml \
  --extra-vars "target_hosts=<node>"
```

## Best Practices

### 1. Test Connectivity First
```bash
ansible -i inventory.ini new_workers -m ping
```

### 2. Use Dry Run Mode
```bash
ansible-playbook -i inventory.ini playbook-join.yml \
  --extra-vars "target_hosts=new_workers" \
  --check --diff
```

### 3. Backup Before Major Changes
```bash
# Backup etcd on controller
ssh controller-1 sudo etcdctl snapshot save /tmp/etcd-backup.db
```

### 4. Monitor During Join
```bash
# In another terminal, watch node status
watch kubectl get nodes

# Watch kubelet logs on new node
ssh new-worker-1 journalctl -u kubelet -f
```

### 5. Label and Taint New Nodes

After joining, you may want to label nodes:

```bash
# Label GPU nodes
kubectl label node gpu-worker-1 node-type=gpu

# Add taints if needed
kubectl taint node new-worker-1 dedicated=special:NoSchedule
```

## Security Considerations

- The join token expires after 24 hours by default
- Tokens are generated fresh for each join operation
- Ensure SSH access is secure (use key-based authentication)
- Consider using Ansible Vault for sensitive variables

## Related Documentation

- [Kubernetes Node Join Documentation](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/#join-nodes)
- [playbook-install.yml](./playbook-install.yml) - Initial cluster setup
- [roles/join](./roles/join/) - Join role implementation
