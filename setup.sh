#!/bin/bash

#cd /tmp/overlay/files
SRC=$(dirname "$BASH_SOURCE")
cd $SRC

chmod a+x hey_wifi hey_wifi.py io_service.py play amp

mkdir -p /usr/local/bin
cp hey_wifi hey_wifi.py io_service.py play amp /usr/local/bin


mkdir -p /usr/local/share/quiet/
cp quiet-profiles.json /usr/local/share/quiet/

cp io.service hey_wifi.service /etc/systemd/system

systemctl enable io
