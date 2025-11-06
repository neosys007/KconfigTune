## Client Installation

### 0. Download Linux Source Code

In Ubuntu 20.04, check the default kernel configuration file under `/boot`, for example `config-5.4.0-137-generic`.  
Use its version tag to download the corresponding source code from the Ubuntu official repository:

```bash
git clone --branch Ubuntu-5.4.0-136.153 --depth 1 git://git.launchpad.net/~ubuntu-kernel/ubuntu/+source/linux/+git/focal KCONFIGTUNE_LINUX_SOURCE
````

`KCONFIGTUNE_LINUX_SOURCE` is the directory where the kernel source will be stored.
You need to set this path as an environment variable in `kconfigtune-collector.service`.

---

### 1. Configure Environment Variables in `kconfigtune-collector.service`

Modify the environment variables in `kconfigtune-collector.service`.
Descriptions of key variables are as follows:

* **XTUNNABLE_PATH**
  Absolute path to the tunable file. It lists the kernel configuration parameters to be tuned (one per line).

* **KCONFIGTUNE_LINUX_SOURCE**
  Absolute path to the Linux source directory (**without a trailing slash**).

* **COUNTER_FILE**
  Absolute path to a file storing a positive integer that indicates the number of training rounds to perform.

* **SERVER_ADDR**
  Training server address in the format `ip:port`.

* **BENCH_OUTPUT**
  Directory for storing Redis benchmark output (**must end with a slash `/`**).
  Each training round overwrites the previous benchmark results.

* **HOST_NAME**
  Host identifier used to differentiate clients. Must match the name used in the server script.

---

### 2. Run `install.sh`

Before execution, review the contents of `install.sh`.
Run it as the root user.

The script performs the following tasks:

```bash
# Install pip and gRPC library
echo 'install pip and grpc library'
apt install -y python3-pip
pip3 install protobuf grpcio pandas
pip3 install --upgrade protobuf

# Install Redis and kernel build dependencies
echo 'install redis and kernel compilation dependencies'
apt install -y redis flex bison libssl-dev libelf-dev dwarves apache2 liblz4-tool zstd libncurses-dev
systemctl enable redis-server.service

# Copy systemd service file and enable it
echo 'copy systemd script and enable it'
cp ./new_systemd/kconfigtune-collector.service /lib/systemd/system
systemctl enable kconfigtune-collector.service
```

---

### 3. Set Training Counter

Write the desired number of training rounds (a positive integer) into the file specified by `COUNTER_FILE`.

This file will be deleted automatically after a complete training cycle;
set it again before the next training.

---

### 4. Reboot

```bash
reboot
```

After reboot, monitor the client’s behavior through the server-side logs.

---

### 5. Configure GRUB Default Entry

```bash
# Check current kernel version
uname -sr

# Find corresponding GRUB menu entry
grep menuentry /boot/grub/grub.cfg

# Edit GRUB default configuration
vi /etc/default/grub

# Set GRUB_DEFAULT to the current kernel entry
update-grub

# For openEuler systems
grub2-set-default
grub2-mkconfig -o /boot/grub2/grub.cfg
```

---

## 6.extKconfig User Guide

### Quick Start

#### 1️⃣ Preparation

1. cp -r ./extKconfig/exKconfig ..
   ```

2. In the top-level `Kconfig` file, add:

   ```makefile
   source "exKconfig/Kconfig"
   ```

3. Optional adjustments:

   * Append a custom suffix to `EXTRAVERSION` in the top-level Makefile to distinguish builds.
   * After modifications, run `git commit`, then `git stash` to revert the source for multiple testing cycles.

---

#### 2️⃣ User Input and Execution

* Edit `input.txt` to follow the `sysctl` format:

  ```
  {parameter_name} = {value}
  ```

* To determine parameter limits:

  ```bash
  sudo python3 param_value.py
  ```

  Output: `modification_results.txt` — containing each parameter’s maximum valid value.

* Run the main modification program:

  ```bash
  sudo python3 exkconfig.py
  ```

* After successful modification, rebuild and install the kernel.


---

### 7. Import `chengeNode` Module

cd src

Parse kernel configuration dependencies and store results in `KCONFIG_PATH`.
Copy the generated `config.json` and `dep.json` to the server directory `~/KconfigTunePerf/data`.

```bash
python checkKconfigDep.py -c <checkfile> -v <kernelversion> -s <sourcecode> -o <output>
```

Parameter explanation:

| Parameter | Description                                              |
| --------- | -------------------------------------------------------- |
| `-c`      | Path to the `.config` file                               |
| `-v`      | Kernel version number                                    |
| `-s`      | Path to the Linux source directory                       |
| `-o`      | Output directory for dependency results (`KCONFIG_PATH`) |

---

## Server Installation

### 1. Install Scikit-Tune Optimization Library

Download from [Scikit-Tune repository](https://isrc.iscas.ac.cn/gitlab/xiansong/ml4sys_tune), then install:

```bash
sudo python3 setup.py install
```

**Notes:**

* The latest version of `ConfigSpace` (0.6.1) has compatibility issues. Use 0.6.0 instead.
* `np.int` has been deprecated since NumPy 1.24. Use an older NumPy version.

---

### 2. Prepare Initial Data Files

Place the following files under `~/KconfigTunePerf/data`:

```
start.config          : base kernel configuration file
tunnable_all          : list of all tunable configuration options
```



