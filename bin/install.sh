#!/bin/bash

# This installs backup to the system
#
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