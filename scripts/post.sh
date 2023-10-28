#!/bin/bash

# Check if an interval is provided as an argument
if [ -z "$1" ]; then
    echo "Usage: $0 <interval_in_seconds>"
    exit 1
fi

# Store the interval from the command line argument
interval="$1"

# Infinite loop to repeatedly run the last command
while true; do
curl -X POST \
"http://localhost:8080/pipeline/7daXjsJHE3cZU/task?token=VBtQYnXjdPsGBM0hifAqePy9Ef2kXPWYChWnNO" \
-H "Content-Type: application/json" \
-d '{"texts":["This is an example text."], "filename":["example.txt"]}'
    sleep "$interval"
done
