#!/bin/bash

dev=$1

if [[ "$dev" == "all" ]]; then
  DEVICES=("6b" "70" "75" "7a" "e8" "ed" "f2" "f7")

elif [[ "$dev" == "single" ]]; then
  DEVICES=("6b")

elif [[ "$dev" == "s0" ]]; then
  DEVICES=("6b" "70" "75" "7a")

elif [[ "$dev" == "s1" ]]; then
  DEVICES=("e8" "ed" "f2" "f7")

else
  echo $dev option not recognized...
  echo Usage: ./monitor_fw_counters.sh \<devices\>
  echo ""
  echo all: all devices
  echo single: only the first device
  echo s0: devices of S0
  echo s1: devices of S1

  exit 1
fi

while(true); do
 echo -e "\t\tdev0\tdev1\tdev2\tdev3\tdev4\tdev5\tdev6\tdev7"
 for i in `seq 0 7`; do
  echo -n "FW request AE ${i}: "
  for d in "${DEVICES[@]}"; do
   cat /sys/kernel/debug/qat_4xxx_0000\:${d}\:00.0/fw_counters | grep "Requests \[AE  ${i}\]" | awk -F':' '{print $2}' | awk '{print $1}' | tr '\n' '\t\t'
  done
  echo ""
 done
 echo -n ""
 sleep 1
 clear
done
