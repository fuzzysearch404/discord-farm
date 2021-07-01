#!/bin/bash

# SCRIPT ARGS
# -----------------
# $1 = Postgres host
# $2 = Postgres database
# $3 = Postgres username
# $4 = Postgres password

# Just in case the local folder does not exist
mkdir backups

BACKUP_FILE_NAME="backups/dump_`date +%H`.gz"
BACKUP_FOLDER="dfarm_backups/`date +%d`"

# Limit the dumps per hours. Btw: PGPASSWORD is a bad practice.
PGPASSWORD="$4" pg_dump -w -c -U "$3" -h "$1" "$2" | gzip > $BACKUP_FILE_NAME
unset PGPASSWORD

# Overwrite the current last month day's hourly backup.
# gupload does not have any other file deletion options and I don't need my
# google drive full of old backups... (I hope so)
gupload $BACKUP_FILE_NAME -c $BACKUP_FOLDER --overwrite

exit 0
