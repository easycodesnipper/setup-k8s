# NVIDIA Container Toolkit Role - Testing Guide

## Test Scenarios

### Scenario 1: Fresh Installation with Existing containerd Config

**Prerequisites:**
- containerd is already installed and configured
- Existing custom configurations in `/etc/containerd/config.toml`

**Test Steps:**
```bash
# 1. Check existing configuration
cat /etc/containerd/config.toml

# 2. Run the role
ansible-playbook -i inventory.ini playbook-install.yml --tags "nvidia-gpu"

# 3. Verify NVIDIA runtime was added
grep -A 5 "nvidia" /etc/containerd/config.toml

# 4. Verify existing configurations are preserved
# (Check your custom settings are still there)

# 5. Check backup was created
ls -la /etc/containerd/config.toml.bak.nvidia.*
```

**Expected Results:**
- ✅ NVIDIA runtime configuration appended to end of file
- ✅ All existing configurations remain unchanged
- ✅ Backup file created with timestamp
- ✅ No duplicate entries on re-run

---

### Scenario 2: Idempotency Test (Run Multiple Times)

**Test Steps:**
```bash
# First run
ansible-playbook -i inventory.ini playbook-install.yml --tags "nvidia-gpu"

# Second run (should detect already configured)
ansible-playbook -i inventory.ini playbook-install.yml --tags "nvidia-gpu"

# Third run
ansible-playbook -i inventory.ini playbook-install.yml --tags "nvidia-gpu"
```

**Expected Results:**
- ✅ First run: Adds NVIDIA configuration
- ✅ Second/Third runs: Detects existing config, skips modification
- ✅ No duplicate configurations
- ✅ Only one backup from first run

---

### Scenario 3: Configuration Verification

**Test Steps:**
```bash
# 1. Verify nvidia-container-runtime binary exists
which nvidia-container-runtime

# 2. Check containerd config has NVIDIA section
grep -A 5 "\[plugins.*nvidia\]" /etc/containerd/config.toml

# 3. Verify containerd can see the runtime
sudo ctr plugins ls | grep nvidia

# 4. Test running a GPU container (if GPU available)
sudo ctr run --runtime io.containerd.runc.v2 \
  --rm docker.io/nvidia/cuda:11.0-base \
  nvidia-test nvidia-smi
```

**Expected Results:**
- ✅ Binary exists at `/usr/bin/nvidia-container-runtime`
- ✅ Configuration shows correct TOML structure
- ✅ containerd recognizes the runtime
- ✅ GPU container runs successfully (if GPU present)

---

### Scenario 4: Rollback Test

**Test Steps:**
```bash
# 1. Note current config
md5sum /etc/containerd/config.toml

# 2. List backups
ls -la /etc/containerd/config.toml.bak.nvidia.*

# 3. Restore from backup
cp /etc/containerd/config.toml.bak.nvidia.<timestamp> /etc/containerd/config.toml

# 4. Restart containerd
systemctl restart containerd

# 5. Verify NVIDIA runtime is removed
grep "nvidia" /etc/containerd/config.toml || echo "NVIDIA config removed"
```

**Expected Results:**
- ✅ Backup exists and is restorable
- ✅ Original configuration restored
- ✅ NVIDIA runtime configuration removed
- ✅ containerd restarts successfully

---

### Scenario 5: Disabled Role Test

**Test Steps:**
```yaml
# In group_vars/all/all.yml
nvidia_container_toolkit_enabled: false
```

```bash
# Run playbook
ansible-playbook -i inventory.ini playbook-install.yml
```

**Expected Results:**
- ✅ Role is skipped
- ✅ No changes to containerd configuration
- ✅ No packages installed
- ✅ Playbook completes successfully

---

## Validation Checklist

After running the role, verify:

- [ ] NVIDIA packages installed: `dpkg -l | grep nvidia-container-toolkit` (Debian) or `rpm -qa | grep nvidia-container-toolkit` (RHEL)
- [ ] Configuration added to `/etc/containerd/config.toml`
- [ ] Existing configurations preserved
- [ ] Backup created: `/etc/containerd/config.toml.bak.nvidia.*`
- [ ] containerd service running: `systemctl status containerd`
- [ ] No errors in containerd logs: `journalctl -u containerd -f`
- [ ] Idempotent: Running again doesn't change anything

---

## Common Issues

### Issue: Permission Denied
**Solution:** Ensure playbook runs with `become: true`

### Issue: containerd Not Found
**Solution:** Run containerd role first or install containerd manually

### Issue: NVIDIA Driver Not Found
**Solution:** Install NVIDIA drivers before running this role
```bash
nvidia-smi  # Should show GPU info
```

### Issue: Configuration Syntax Error
**Solution:** Check TOML syntax
```bash
# Validate TOML syntax
python3 -c "import toml; toml.load('/etc/containerd/config.toml')"
```
