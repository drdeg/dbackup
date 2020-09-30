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

function log () {
    # log level "Message"
    re='^[0-9]+$'
    case ${1^^} in
    VERBOSE|DEBUG|INFO|WARNING|ERROR)
        # First argument is log level
        echo "${@:2}"
        ;;
    *)
        echo "${@}"
        ;;
    esac
}

function install_packages() {
    # Usage:
    #
    # install_packages pkg1 pkg2 pkg3
    #
    local PACKAGES_TO_INSTALL=()
    for package in "${@}"
    do
        if dpkg -s $package > /dev/null 2>&1
        then
            log DEBUG "Package \"$package\" is installed"
        else
            log INFO "Installing package \"$package\""
            PACKAGES_TO_INSTALL+=($package)
        fi
    done

    if [[ $PACKAGES_TO_INSTALL ]]
    then
        if sudo apt-get install -y ${PACKAGES_TO_INSTALL[@]}
        then
            log INFO "Package installation successfull"
        else
            log ERROR "Package installation failed. Aborting installation."
            exit 101
        fi
    fi

}

function print_usage()
{
    echo "DBackup installer"
    echo " install.sh dest"
    echo ""
    echo "  dest  full path to install destination"
}

function create_python_venv() 
{
    echo "Nada"
}


# Parse arguments
DEST=
CLEAN_DEST=
UPGRADE=
while [[ $# -gt 0 ]]
do
    case "$1" in
    -h|--help)
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
    --upgrade)
        UPGRADE=--upgrade
        ;;
    --clean)
        CLEAN_DEST=true
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

if [[ ! ${DEST} ]]
then
    log ERROR "Destination was not specified"
    print_usage
    exit 1
fi

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

# Install required packages
install_packages python3 python3-pip python3-venv

# Determine source dir
SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
SRC_BASE="$(readlink -m ${SCRIPTDIR}/..)"

# Create the python venv
# This requires python3-venv and python3-pip

# Copy relevant files

if [[ ${CLEAN_DEST} ]]
then
    echo "Cleaning ${DEST}"
    ${SUDO} rm -rf "${DEST}"
fi

# Create destination directory if it doesn't exist
[[ -d ${DEST} ]] || ${SUDO} mkdir ${DEST}

# Copy files
${SUDO} cp -R ${SRC_BASE}/dbackup/* ${DEST}/.
${SUDO} cp -R ${SRC_BASE}/systemd ${DEST}/systemd
${SUDO} cp ${SRC_BASE}/bin/dbackup.sh ${DEST}/dbackup

# Create python venv
VENV_DIR="${DEST}/pyvenv"
if [[ ! -d "${VENV_DIR}" ]]
then
    log INFO "Creating python virtual environment in ${VENV_DIR}"
    ${SUDO} python3 -m venv "${VENV_DIR}"
fi

# Install python requirements
if [[ -e ${VENV_DIR}/pyvenv.cfg ]]
then
    # activate python environment
    #source "${VENV_DIR}/bin/activate"

    ${SUDO} "${VENV_DIR}/bin/python3" -m pip install ${UPGRADE} pip wheel
    ${SUDO} "${VENV_DIR}/bin/python3" -m pip install ${UPGRADE} -r ${DEST}/requirements.txt
else
    log ERROR "Failed to install python environment in ${VENV_DIR}"
    exit 1
fi

log INFO "Successfully installed!"


