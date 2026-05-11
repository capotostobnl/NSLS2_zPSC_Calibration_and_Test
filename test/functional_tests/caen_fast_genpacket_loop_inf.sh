#!/bin/bash

# Run ./caen_fast_genpacket at 10Hz (every 0.1 seconds)

for ((; ;)); do
    ./caen_fast_genpacket
    sleep 0.01
done

