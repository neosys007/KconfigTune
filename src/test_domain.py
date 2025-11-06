import libvirt
import guestfs
from threading import Thread
import time
import subprocess

global finished
finished = False

def timeoutEventCallback(timer, opaque):
    global finished
    finished = True

def lifecycle_callback (connection, domain, event, detail, console):
    name = domain.name()
    state = domain.state()
    print("%s transitioned to state %d, reason %d, event %d, detail %d\n"
          % (name, state[0], state[1], event, detail))
    if event == libvirt.VIR_DOMAIN_EVENT_SHUTDOWN:
        finished = True
        print("%s shutdowned\n" % name)

def bootDomain(vmName, timeout):
    libvirt.virEventRegisterDefaultImpl()

    # 连接到qemu
    conn = None
    try:
        conn = libvirt.open("qemu:///system")
    except libvirt.libvirtError as e:
        print(repr(e), file=sys.stderr)
        exit(1)


    # 定位到名为vmName的虚拟机
    dom = conn.lookupByName(vmName)
    if dom == None:
        print('Failed to get the domain object', file=sys.stderr)

    timer_id = libvirt.virEventAddTimeout(timeout*1000, timeoutEventCallback, None)

    # 注册事件回调函数，监控虚拟机退出事件
    conn.domainEventRegister(lifecycle_callback, None)

    # 启动虚拟机
    dom.create()
    print("created")

    while(not finished):
        if(libvirt.virEventRunDefaultImpl() < 0):
            print("error\n")

    libvirt.virEventRemoveTimeout(timer_id)

    # 关闭连接
    conn.close()

def installKernel(vmName, packageDir):
    subprocess.run('rm -rf /tmp/kernel_packages', shell=True)
    subprocess.run('cp -r %s /tmp/kernel_packages' % packageDir, shell=True)
    command = 'virt-customize \
                    -d focal \
                    --delete /mnt/kernel_packages \
                    --copy-in /tmp/kernel_packages:/mnt  \
                    --run-command \'dpkg -i /mnt/kernel_packages/*.deb\''
    subprocess.run(command, shell=True)



if __name__ == '__main__':
    vmName = 'focal'
    packageDir = '/home/pan/os/tunning/kernel_packages'
    installKernel(vmName, packageDir)
    bootDomain(vmName, 120)
