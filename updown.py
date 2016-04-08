#!/usr/bin/env python3

import os
import subprocess as sp

#import sys
#for key in os.environ.keys():
#    print("%30s %s \n" % (key,os.environ[key]))
#sys.exit(1)

def call(cmd, args):
    cmd = cmd.split(" ")
    j = 0
    for i in range(len(cmd)):
        if cmd[i] == "?":
            cmd[i] = str(args[j])
            j += 1

    sp.check_call(cmd)


def mask_to_cidr(mask):
    tmp = "".join([format(int(x), "08b") for x in mask.split(".")])
    return len(tmp.partition("0")[0])


script_type = os.getenv("script_type")
assert script_type in ("up", "down")

device = os.getenv("dev")
tun_mtu = int(os.getenv("tun_mtu"))

v4_addr = os.getenv("ifconfig_local")
v4_mask = os.getenv("ifconfig_netmask")
v4_gateway = os.getenv("route_vpn_gateway")

dns = []
domain = None
for i in range(1,99):
    o = os.getenv("foreign_option_%d" % i)
    if o is None:
        break
    elif o.startswith("dhcp-option DNS"):
        dns_ip = o.partition(" DNS ")[2]
        dns.append(dns_ip)
    elif o.startswith("dhcp-option DOMAIN"):
        domain = o.partition(" DOMAIN ")[2]


namespace = "ns1"
namespace_dir = os.path.join("/etc/netns", namespace)
dns_config = os.path.join(namespace_dir, "resolv.conf")

if script_type == "up":
    # create namespace
    try:
        call("ip netns add ?", (namespace,))
    except:
        # ignore if namespace exists
        pass

    # configure firewall in namespace
    call("ip netns exec ? iptables -F", (namespace,))
    call("ip netns exec ? iptables -I INPUT -j DROP", (namespace,))
    call("ip netns exec ? iptables -I FORWARD -j DROP", (namespace,))
    call("ip netns exec ? iptables -I INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT", (namespace,))
    call("ip netns exec ? iptables -I INPUT -i lo -j ACCEPT", (namespace,))
    call("ip netns exec ? ip6tables -F", (namespace,))
    call("ip netns exec ? ip6tables -I INPUT -j DROP", (namespace,))
    call("ip netns exec ? ip6tables -I INPUT -i lo -j ACCEPT", (namespace,))
    call("ip netns exec ? ip6tables -I FORWARD -j DROP", (namespace,))
    call("ip netns exec ? ip6tables -I OUTPUT -j DROP", (namespace,))
    call("ip netns exec ? ip6tables -I OUTPUT -o lo -j ACCEPT", (namespace,))

    # move device to namespace
    call("ip link set ? netns ?", (device, namespace))

    # enable loopback device in namespace
    call("ip netns exec ? ip link set lo up", (namespace,))

    # enable device
    call("ip netns exec ? ip link set ? up", (namespace, device))

    # set mtu
    call("ip netns exec ? ip link set dev ? mtu ?", (namespace, device, tun_mtu))

    # configure v4 address
    address = "%s/%d" % (v4_addr, mask_to_cidr(v4_mask))
    call("ip netns exec ? ip addr change ? dev ?", (namespace, address, device))

    # add default route
    call("ip netns exec ? ip route add default via ?", (namespace, v4_gateway))

    # configure dns
    if not os.path.exists(namespace_dir):
        os.makedirs(namespace_dir)
    with open(dns_config, "w") as fh:
        if domain is not None:
            fh.write("domain " + domain + "\n")
        for d in dns:
            fh.write("nameserver " + d + "\n")

if script_type == "down":
    # delete namespace
    call("ip netns delete ?", (namespace,))

    # unconfigure dns
    os.remove(dns_config)
    os.rmdir(namespace_dir)

