#!/bin/bash

# Specify the password file path
PASS_FILE="$HOME/.passkeys/rpi.txt"

#check if the password file exists
if [ ! -f $PASS_FILE ]; then
    echo "Password file not found"
    exit 1
fi

PASSWORD=$(cat $PASS_FILE)

# Check if the password is empty
if [ -z $PASSWORD ]; then
    echo "Password is empty"
    exit 1
fi

SSH_USER="test"
SSH_HOST="192.168.1.184"
# Connect to the Raspberry Pi

# print status
echo "Connecting to the Raspberry Pi"
sshpass -p $PASSWORD ssh $SSH_USER@$SSH_HOST

