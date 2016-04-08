#!/bin/bash
USR=$(whoami)
sudo ip netns exec ns1 sudo -iu $USR
