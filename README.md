# OpenVPN Client with a Network Namespace
This repository contains configuration and script files to use the OpenVPN
client with Linux network namespaces.

Upon connecting with OpenVPN, the VPN's virtual NIC is moved to a dedicated
network namespace named `ns1`. This configuration has the following useful
properties:
 * Applications inside `ns1` can only communicate through the VPN's NIC.
 * Applications outside `ns1` can not access the VPN's NIC.
 * If the VPN connection terminates, `ns1` will loose network access.

### Usage
Adjust `vpn.conf` to fit your OpenVPN setup. Then start the OpenVPN client,
i.e. `sudo openvpn --config vpn.conf`. Finally, use `shell.sh` to obtain a
terminal in the network namespace and run some applications.

### Contents
 * `vpn.conf` is a skeleton OpenVPN config. It only contains the configuration
   options to make use of network namespaces. You have to add your own OpenVPN
   configuration.
 * `updown.py` is the script called by OpenVPN to setup and teardown the
   virtual NIC. It sets up the network namespace, virtual NIC, DNS and
   iptables.
 * `shell.sh` is a utility script to spawn a terminal inside the network
   namespace.
 * `firefox.sh` is a utility script to spawn Firefox inside the network
   namespace.

### TODOs
These are some bugs or possible improvements that are not yet addressed:
 * Make the name of the network namespace configurable or dynamic.
 * Investigate why applications running inside the namespace permanently loose
   network access on OpenVPN restarts/reconnects.
 * Clean up and document the code.
 * Add support for IPv6.
 * Add support for routes other than the default gateway.

