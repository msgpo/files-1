#!/bin/bash

#cd /tmp/overlay/files
SRC=$(dirname "$BASH_SOURCE")
cd $SRC

chmod +x hey_wifi hey_wifi.py io_service.py

mkdir -p /usr/local/bin
cp hey_wifi /usr/local/bin
cp hey_wifi.py /usr/local/bin
cp io_service.py /usr/local/bin

mkdir -p /usr/local/share/quiet/
cp quiet-profiles.json /usr/local/share/quiet/

cp io.service /etc/systemd/system
cp hey_wifi.service /etc/systemd/system

systemctl enable io
