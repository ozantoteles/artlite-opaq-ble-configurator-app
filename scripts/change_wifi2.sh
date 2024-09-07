#!/bin/bash
 
SSID="$1"
PASSWORD="$2"
 
WPA_CONFIG="ctrl_interface=/var/run/wpa_supplicant\nctrl_interface_group=0\nupdate_config=1\nnetwork={\n\tssid=\"$SSID\"\n\tpsk=\"$PASSWORD\"\n}"
 
WPA_CONFIG_FILE="/etc/wpa_supplicant.conf"
WPA_CONFIG_FILE_FLUSH="/mnt/datafs/lucan/lucan_wifi_list.conf"
 
if [[ $SSID == "" || $PASSWORD == "" ]]; then
    echo "Fail: ssid or password is empty"
else
    echo -e $WPA_CONFIG > $WPA_CONFIG_FILE
    echo -e $WPA_CONFIG > $WPA_CONFIG_FILE_FLUSH
    echo "Success"
fi