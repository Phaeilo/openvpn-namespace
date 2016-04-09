#!/usr/bin/env python3

import os
import sys
import shlex
import subprocess


NAMESPACE = "ns1"
DEBUG_ENV = False


if DEBUG_ENV:
    # print all environment variables and exit
    # useful for debugging what configuration data is made available by OpenVPN
    for key in os.environ.keys():
        sys.stderr.write("%30s %s \n" % (key, os.environ[key]))
    sys.exit(1)


def call(cmd, args):
    """
    Run the command specified in cmd. Arguments consisting of a single ? are
    replaced with the corresponding value from args. This function returns if
    the command was executed successfully. If the command caused an error, an
    exception is thrown.
    """

    # split command into its arguments
    assert cmd is not None
    cmd = shlex.split(cmd)

    # replace placeholders with contents from args
    j = 0
    for i in range(len(cmd)):
        if cmd[i] == "?":
            cmd[i] = str(args[j])
            j += 1

    # run command
    subprocess.check_call(cmd)


def mask_to_cidr(mask):
    """
    Determine the CIDR suffix for a given dotted decimal IPv4 netmask.
    """
    # convert netmask to 32 binary digits
    tmp = "".join([format(int(x), "08b") for x in mask.split(".")])
    # count leading ones
    return len(tmp) - len(tmp.lstrip("1"))


# VPN connection setUP or tearDOWN
script_type = os.getenv("script_type")
assert script_type in ("up", "down")

# NIC properties
device = os.getenv("dev")
tun_mtu = int(os.getenv("tun_mtu"))

# IPv4 configuration
v4_addr = os.getenv("ifconfig_local")
v4_mask = os.getenv("ifconfig_netmask")
v4_gateway = os.getenv("route_vpn_gateway")

# DNS configuration
dns_servers = []
domain = None
i = 1
while True:
    o = os.getenv("foreign_option_%d" % i)
    i += 1

    if o is None:
        break

    elif o.startswith("dhcp-option DNS"):
        dns_ip = o.partition(" DNS ")[2]
        dns_servers.append(dns_ip)

    elif o.startswith("dhcp-option DOMAIN"):
        domain = o.partition(" DOMAIN ")[2]

# setup
if script_type == "up":
    # create namespace
    try:
        call("ip netns add ?", (NAMESPACE,))
    except:
        # ignore if namespace exists
        pass

    def nsexec(cmd, args=()):
        cmd = "ip netns exec ? " + cmd
        args = (NAMESPACE,) + args
        call(cmd, args)

    # configure firewall in namespace
    nsexec("iptables -F")
    nsexec("iptables -I INPUT -j DROP")
    nsexec("iptables -I FORWARD -j DROP")
    nsexec("iptables -I INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT")
    nsexec("iptables -I INPUT -i lo -j ACCEPT")
    nsexec("ip6tables -F")
    nsexec("ip6tables -I INPUT -j DROP")
    nsexec("ip6tables -I INPUT -i lo -j ACCEPT")
    nsexec("ip6tables -I FORWARD -j DROP")
    nsexec("ip6tables -I OUTPUT -j DROP")
    nsexec("ip6tables -I OUTPUT -o lo -j ACCEPT")

    # move device to namespace
    call("ip link set ? netns ?", (device, NAMESPACE))

    # enable loopback device in namespace
    nsexec("ip link set lo up")

    # enable device
    nsexec("ip link set ? up", (device,))

    # set mtu
    nsexec("ip link set dev ? mtu ?", (device, tun_mtu))

    # configure v4 address
    address = "%s/%d" % (v4_addr, mask_to_cidr(v4_mask))
    nsexec("ip addr change ? dev ?", (address, device))

    # add default route
    nsexec("ip route add default via ?", (v4_gateway,))

    # configure DNS
    namespace_dir = os.path.join("/etc/netns", NAMESPACE)
    if not os.path.exists(namespace_dir):
        os.makedirs(namespace_dir)

    dns_config = os.path.join(namespace_dir, "resolv.conf")
    with open(dns_config, "w") as fh:
        if domain is not None:
            fh.write("domain " + domain + "\n")
        for dns_server in dns_servers:
            fh.write("nameserver " + dns_server + "\n")

# teardown
if script_type == "down":
    # delete namespace
    call("ip netns delete ?", (NAMESPACE,))

    # unconfigure DNS
    namespace_dir = os.path.join("/etc/netns", NAMESPACE)
    dns_config = os.path.join(namespace_dir, "resolv.conf")
    os.remove(dns_config)
    os.rmdir(namespace_dir)
