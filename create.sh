#!/bin/bash

iptables -A INPUT -i docker0 -p tcp --dport 2593 -j ACCEPT
iptables -A INPUT -i docker0 -p tcp --dport 1234 -j DROP
