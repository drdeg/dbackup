#!/bin/bash

# This installs backup to the system
#
# Installation procedure:
#  1. Download the source code from github:
#     git clone git@github.com:drdeg/dbackup.git
#  2. Run the install script in bin/install.sh
#
# Destination folder hierarchy:
# DEST
#  +- configurations  Sample configuration files
#  +- dbackup         Folder containing the python code for DBackup
#  +- pyvenv          Virtual python environment
#  +- systemd         Sample systemd unit files (service and timer)
#  +- dbackup.sh      Script for running dbackup
#
#
# Installation does the following
#
#  - Check if the destination requires root
#  - Create a python virtual environment at the destination
#  - Copies all relevant files to the specified destination
#  - Updates systemd unit files to reflect the installation paths

function print_usage()
{
    echo "DBackup installer"
    echo " install.sh dest"
    echo ""
    echo "  dest  full path to install destination"
}

fucntion create_python_venv() 
{
    
}


# Parse arguments
DEST=
while [[ $# -gt 0 ]]
do
    case "$1" in
    -h)
        print_usage
        exit 0
        ;;
    --home)
        HOME_BASE=$2
        shift
        ;;
    --backup)
        ENABLE_BACKUP=true
        ;;
    *)
        if [[ ! $DEST ]]
        then
            DEST=${1}
        else
            echo "Expected only one destination"
            print_usage
            exit 56
        fi
    esac
    shift
done

# Check if the destination requires root permissions
PARENT=$(dirname "${DEST}")
OWNER=$(stat -c '%U' "${PARENT}")

if [[ "${OWNER}" == "root" ]]
then
    echo "Installing dbackup as root"
    SUDO="sudo"
else
    SUDO=""
fi

# Create the python venv
# This requires python3-venv and python3-pip

# Copy relevant files

