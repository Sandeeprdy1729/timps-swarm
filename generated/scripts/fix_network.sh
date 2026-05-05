#!/bin/bash
# TIMPS Network Medic — Common Fixes (DRY RUN)

# Flush DNS cache (macOS)
# sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder

# Flush DNS cache (Linux systemd-resolve)
# sudo systemd-resolve --flush-caches

# Reset WiFi (macOS)
# networksetup -setairportpower en0 off && networksetup -setairportpower en0 on

# Test if port is open on a host
# nc -zv <host> <port>

# Release and renew DHCP (macOS)
# sudo ipconfig set en0 DHCP