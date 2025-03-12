#!/bin/bash

# Specify the password file path
PASS_FILE="$HOME/.passkeys/rpi.txt"

# Check if the password file exists
if [ ! -f "$PASS_FILE" ]; then
    echo "Password file not found"
    exit 1
fi

PASSWORD=$(cat "$PASS_FILE")

# Check if the password is empty
if [ -z "$PASSWORD" ]; then
    echo "Password is empty"
    exit 1
fi

SSH_USER="test"
SSH_HOST="192.168.1.184"

# Get local machine time in proper format (YYYY-MM-DD HH:MM:SS)
LOCAL_TIME=$(date +"%Y-%m-%d %H:%M:%S")

echo "Updating Raspberry Pi clock to local time: $LOCAL_TIME"
# Update the Pi's clock and write it to the hardware clock.
sshpass -p "$PASSWORD" ssh "$SSH_USER@$SSH_HOST" "sudo date -s '$LOCAL_TIME'"

echo "Connecting to the Raspberry Pi"
sshpass -p "$PASSWORD" ssh "$SSH_USER@$SSH_HOST"
