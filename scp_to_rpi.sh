#!/bin/bash

# Script to scp -r a directory to the Raspberry Pi

# Check that source is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <source>"
    exit 1
fi

# Source is first arguement
SOURCE=$1

# Define User and Host
SSH_USER="test"
SSH_HOST="192.168.1.184:/home/test/"

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

# print status
echo "Copying to the Raspberry Pi"

sshpass -p $PASSWORD scp -r $SOURCE $SSH_USER@$SSH_HOST