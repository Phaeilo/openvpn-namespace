#!/bin/bash
USR=$(whoami)
sudo ip netns exec ns1 sudo -u $USR bash -c 'firefox &> /dev/null &'
