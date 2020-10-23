# Not an actual setup file. Do this manually. (should create actual setup file some day)

sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt install -y redis-server
# sudo nano /etc/redis/redis.conf  ==> supervised no -> (change to) supervised systemd.
# sudo systemctl restart redis.service
sudo apt install -y postgresql postgresql-contrib
sudo apt install -y python3.8-dev
sudo apt install -y python3-pip
python3.8 -m pip install discord.py
python3.8 -m pip install asyncpg
python3.8 -m pip install aioredis
python3.8 -m pip install psutil
python3.8 -m pip install websockets
python3.8 -m pip install requests
sudo timedatectl set-timezone UTC

# sudo su - postgres
# psql

# CREATE USER discordfarm WITH PASSWORD 'pass';
# CREATE DATABASE discordfarmdata;

# Create database with schema.sql or import an existing backup.