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


def nsexec(cmd, args=()):
    """
    Run a command in a network namespace.
    """

    cmd = "ip netns exec ? " + cmd
    args = (NAMESPACE,) + args
    call(cmd, args)


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

# IPv6 configuration
v6_addr = os.getenv("ifconfig_ipv6_local")
v6_netbits = os.getenv("ifconfig_ipv6_netbits")
v6_gateway = os.getenv("ifconfig_ipv6_remote")
v6_available = v6_addr is not None \
        and v6_netbits is not None \
        and v6_gateway is not None

# DNS configuration
dns_servers = []
i = 1
while True:
    o = os.getenv("foreign_option_%d" % i)
    i += 1

    if o is None:
        break

    elif o.startswith("dhcp-option DNS"):
        dns_ip = o.partition(" DNS ")[2]
        dns_servers.append(dns_ip)

# setup
if script_type == "up":
    # create namespace
    try:
        call("ip netns add ?", (NAMESPACE,))
    except:
        # ignore if namespace exists
        pass

    # flush routing table
    nsexec("ip route flush table all")

    # configure firewall in namespace
    nsexec("iptables -F")
    nsexec("iptables -I INPUT -j DROP")
    nsexec("iptables -I FORWARD -j DROP")
    nsexec("iptables -I INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT")
    nsexec("iptables -I INPUT -i lo -j ACCEPT")
    nsexec("iptables -I OUTPUT -j DROP")
    nsexec("iptables -I OUTPUT -o lo -j ACCEPT")
    nsexec("iptables -I OUTPUT -d 10.0.0.0/8 -j DROP")
    nsexec("iptables -I OUTPUT -d 172.16.0.0/12 -j DROP")
    nsexec("iptables -I OUTPUT -d 192.168.0.0/16 -j DROP")
    nsexec("iptables -I OUTPUT -o ? -j ACCEPT", (device,))
    nsexec("ip6tables -F")
    nsexec("ip6tables -I INPUT -j DROP")
    nsexec("ip6tables -I INPUT -i lo -j ACCEPT")
    nsexec("ip6tables -I FORWARD -j DROP")
    nsexec("ip6tables -I OUTPUT -j DROP")
    nsexec("ip6tables -I OUTPUT -o lo -j ACCEPT")
    if v6_available:
        nsexec("ip6tables -I INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT")
        nsexec("ip6tables -I OUTPUT -o ? -j ACCEPT", (device,))

    # create directory for resolv.conf
    namespace_dir = os.path.join("/etc/netns", NAMESPACE)
    if not os.path.exists(namespace_dir):
        os.makedirs(namespace_dir)

    # create resolv.conf
    dns_config = os.path.join(namespace_dir, "resolv.conf")
    with open(dns_config, "w") as fh:
        for dns_server in dns_servers:
            fh.write("nameserver " + dns_server + "\n")

    # move device to namespace
    call("ip link set ? netns ?", (device, NAMESPACE))

    # start/restart loopback device in namespace
    nsexec("ip link set lo down")
    nsexec("ip link set lo up")

    # enable device
    nsexec("ip link set ? up", (device,))

    # set mtu
    nsexec("ip link set dev ? mtu ?", (device, tun_mtu))

    # configure v4
    address = "%s/%d" % (v4_addr, mask_to_cidr(v4_mask))
    nsexec("ip addr change ? dev ?", (address, device))
    nsexec("ip route add default via ?", (v4_gateway,))

    # configure v6, if any
    if v6_available:
        address = "%s/%s" % (v6_addr, v6_netbits)
        nsexec("ip -6 addr change ? dev ?", (address, device))
        nsexec("ip -6 route add default via ?", (v6_gateway,))


# teardown
if script_type == "down":
    # OpenVPN already removed its NIC
    # the namespace is not deleted, because some applications may still use it

    # unconfigure DNS
    namespace_dir = os.path.join("/etc/netns", NAMESPACE)
    dns_config = os.path.join(namespace_dir, "resolv.conf")
    os.remove(dns_config)
    os.rmdir(namespace_dir)
