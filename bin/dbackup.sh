#!/bin/sh
#
# Thin wrapper for running dbackup within a venv

SCRIPTDIR="$( cd "$( dirname "${0}" )" >/dev/null && pwd )"

# Source the virtual environment
source ${SCRIPTDIR}/pyvenv/bin/activate

# Invoke python
python3 ${SCRIPTDIR}/dbackup.py