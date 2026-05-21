#!/bin/bash

# Run ./caen_fast_genpacket at 100Hz (every 0.01 seconds)
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
for ((; ;)); do
    "$SCRIPT_DIR/caen_fast_genpacket"
    sleep 0.01
done

