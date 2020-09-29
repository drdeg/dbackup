# dbackup
My elegant (?!?) backup script.

## Background
According to my wife, I can be paranoid about (data) security. I'm not sure she's right, but I have
set up a simple Linux server at my parents house to mirror important files, like my mp3 collection and
photo albums. I chose this setup as the data would survive if my house burnt to the ground. Keeping
a copy on an external hard drive wouldn't be good enough then.

I also wanted the possiblity to go back to previous states. For instance, if I accidently removed
all photos from 2005, I'd be rather annoyed with myself. So, the system now keeps daily and monthly
snapshots. The snapshots are implemented with hard links, so they come relatively cheap, at least
in terms of storage requirements.

I did'n go for a cloud storage solution, simply because these were not available at the time. 

The first implementation was a bash script, but I rewrote it in Python the other year as the script
became quite complicated when I wanted to report status over MQTT as well.

## Features

- Backup files to local and remote locations
- Simple configuratio with ini-ish-files
- Use ssh and key authentication for security
- Keep n last daily backups
- Keep m last monthly backups

# Installation

- Clone the repository
- Run bin/install.sh

# Usage

Currently, the only documentation is to run ```dbackup.py --help```.
TODO: Write usage instructions

## Configuration

Best way to learn the configuration is perhaps to study the example in the configurations directory. 
Anyway, a ini-file-ish format is used, where each section corresponds to a backup job, with two exceptions:
 - The ```[DEFAULT]``` section is used to specify parameters that apply to all backup jobs. Useful if you
   have same archiving policies for all backup jobs
 - The ```[common]``` section is used to specify variables that can be used in the other sections.

TODO: Document the parameters in the configuration file
