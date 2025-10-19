#!/bin/bash

# Simple shell script wrapper for traffic generation
# Usage: ./generate-traffic.sh [num_users] [duration]

USERS=${1:-5}
DURATION=${2:-60}

echo "Starting traffic generation..."
echo "Concurrent users: $USERS"
echo "Session duration: $DURATION seconds"
echo ""

python3 generate-traffic.py --users "$USERS" --duration "$DURATION"
