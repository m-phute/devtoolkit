#!/bin/bash

function displayHelp(){
   echo "Usage: $0 [utility] [optional args]"
   echo "QAT utility script"
   echo "Run with root privilege"
   echo "Utility args"
   echo "   -m | -monitor"
   echo "   -t | -telemetry"
   echo "   -c | -config"
   echo "Optional args:"
   echo "Args depends on the utility selected"
   echo " -m/-monitor:"
   echo "   -No arg required"
   echo " -t/-telemetry:"
   echo "   -l | -launch"
   echo "   -s | -stop"
   echo "   -o | -output <output directory for the logs>"
   echo " -c/-config:"
   echo "   --dev-acces <0/1>"
   echo "   --section-name <SSL/SHIM>"
   echo "   --services-enabled <sym/asym/dc>"
   echo "   --processes <0..64>"
   echo "   --cy-instances <0..64>"
   echo "   --dc-instances <0..64>"
   echo ""
   echo "Examples:"
   echo " $0 -monitor"
   echo " $0 -telemetry [-l/-s] -o /mnt/drive/logs"
   echo " $0 -config --dev-acces 0 --section-name SHIM --services-enabled asym --processes 32 --cy-instances 2"
   exit 3
}

function handleArgs() {
 MONITOR=false
 TELEMETRY=false
 CONFIG=false
 LAUNCH=false
 STOP=false
 CY_INSTANCES=0
 DC_INSTANCES=0
 PROCESSES=0

 if [ "$1" = "--h" ] || [ "$1" = "-help" ] || [ "$1" = "--help" ] || [ "$1" = "help" ]; then
  displayHelp $0
 fi

 if [[ $EUID -ne 0 ]]; then
  echo "Please run this script with root privilege"
  exit 1
 fi

 options=$(getopt -a -o mtclso: -l monitor,telemetry,config,launch,stop,output:,dev-access:,section-name:,services-enabled:,cy-instances:,dc-instances:,processes: -- "$@")
 set -- $options

 while [ $# -gt 0 ]; do
   case "$1" in
   h|\?)
     displayHelp $0
     ;;
   -m|--monitor) MONITOR=true;
     ;;
   -t|--telemetry) TELEMETRY=true;
     ;;
   -c|--config) CONFIG=true;
     ;;
   -l|--launch) LAUNCH=true;
     ;;
   -s|--stop) STOP=true;
     ;;
   -o|--output) eval OUTPUT=$2; shift 1;
     ;;
   --dev-access) eval DEV_ACCESS=$2; shift 1;
     ;;
   --section-name) eval SECTION_NAME=$2; shift 1;
     ;;
   --services-enabled) eval SERVICES_ENABLED=$2; shift 1;
     ;;
   --cy-instances) eval CY_INSTANCES=$2; shift 1;
     ;;
   --dc-instances) eval DC_INSTANCES=$2; shift 1;
     ;;
   --processes) eval PROCESSES=$2; shift 1;
     ;;
   (--) shift; break;;
   (-*) displayHelp ;;
   (*) break;;
   esac
   shift
 done

 if [ ${MONITOR} == true ] && [ ${TELEMETRY} == false ] && [ ${CONFIG} == false ]; then
  monitor
 elif [ ${MONITOR} == false ] && [ ${TELEMETRY} == true ] && [ ${CONFIG} == false ]; then
  telemetry
 elif [ ${MONITOR} == false ] && [ ${TELEMETRY} == false ] && [ ${CONFIG} == true ]; then
  echo "Configuring QAT devices with:"
  echo -e "DEV_ACCESS: \t${DEV_ACCESS}"
  echo -e "SECTION_NAME: \t${SECTION_NAME}"
  echo -e "SERVICES: \t${SERVICES_ENABLED}"
  echo -e "CY_INSTANCES: \t${CY_INSTANCES}"
  echo -e "DC_INSTANCES: \t${DC_INSTANCES}"
  echo -e "PROCESSES: \t${PROCESSES}"
  configDevices > /dev/null 2>&1
  adf_ctl restart
  echo "QAT Devices configuration completed"
 else
  displayHelp $0
 fi
}

function configDevices(){
  CONFIG_FILE="${CONFIG_FILE:-/etc/4xxx_dev?.conf}"

  for ICP_ROOT in /opt/intel/QAT /QAT; do
   USDM="$ICP_ROOT/build/usdm_drv.ko"
   [ -e "$USDM" ] && break || continue
  done

  if [ ! -e "$USDM" ]; then
   echo "Failed to locate usdm_drv.ko"
   exit 3
  fi

  nodeids=($("$ICP_ROOT/build/adf_ctl" status | grep qat_dev | sed -e 's/.*node_id: //' -e 's/,.*//'))
  DEVICES=${DEVICES:-${#nodeids[*]}}

  if [ $PROCESSES -gt 64 ]; then echo "Can't use more than 64 processes"; displayHelp; fi

  if [ $(( $CY_INSTANCES * $PROCESSES )) -gt 64 ]; then
      CY_INSTANCES=$(( 64 / $PROCESSES)) 
  fi

  if [ $(( $DC_INSTANCES * $PROCESSES )) -gt 64 ]; then
      DC_INSTANCES=$(( 64 / $PROCESSES)) 
  fi

  for d in $(seq 0 $(( $DEVICES - 1 ))); do
    config_file="${CONFIG_FILE/\?/$d}"

    echo "=== $config_file ==="
    tee "$config_file" <<EOF
[GENERAL]
ServicesEnabled = ${SERVICES_ENABLED//,/;}
ConfigVersion = 2
NumCyAccelUnits = 0
NumDcAccelUnits = 6
NumInlineAccelUnits = 0
CyNumConcurrentSymRequests = 512
CyNumConcurrentAsymRequests = 64
DcNumConcurrentRequests = 512
statsGeneral = 1
statsDh = 1
statsDrbg = 1
statsDsa = 1
statsEcc = 1
statsKeyGen = 1
statsDc = 1
statsLn = 1
statsPrime = 1
statsRsa = 1
statsSym = 1
statsMisc = 1
AutoResetOnError = 0

[KERNEL]
NumberCyInstances = 0
NumberDcInstances = 0

[$SECTION_NAME]
NumberCyInstances = $CY_INSTANCES
NumberDcInstances = $DC_INSTANCES
NumProcesses = $PROCESSES
LimitDevAccess = $DEV_ACCESS
EOF

    for cy in $(seq 0 $(( $CY_INSTANCES - 1 ))); do
      #getCore cy ${nodeids[$d]}
      if [ ${nodeids[$d]} -eq 0 ]; then
        core_id="0-59"

      elif [ ${nodeids[$d]} -eq 1 ]; then
        core_id="60-119"
      fi

      tee -a "$config_file" <<EOF
Cy${cy}Name = "Cy${cy}"
Cy${cy}IsPolled = 1
Cy${cy}CoreAffinity = $core_id
EOF
    done

    for dc in $(seq 0 $(( $DC_INSTANCES - 1 ))); do
      #getCore dc ${nodeids[$d]}
      if [ ${nodeids[$d]} -eq 0 ]; then
        core_id="0-59"
      elif [ ${nodeids[$d]} -eq 1 ]; then
        core_id="60-119"
      fi

      tee -a "$config_file" <<EOF
Dc${dc}Name = "Dc${dc}"
Dc${dc}IsPolled = 1
Dc${dc}CoreAffinity = $core_id
EOF

    done
done
}

function getCore(){
  coreids=($(lscpu -e=NODE,CPU | awk -v n=$2 '$1==n{print$2}'))
  eval "q=\$ct_${1}_${2}"
  core_id=${coreids[$q]}
  eval "ct_${1}_${2}=$((q+1))"
}

function monitor(){
 readDevices
 while(true); do
  echo -e "\t\tdev0\tdev1\tdev2\tdev3\tdev4\tdev5\tdev6\tdev7"
  for i in `seq 0 7`; do
   echo -n "FW request AE ${i}: "
   for device in "${arrayDevices[@]}"; do
    cat /sys/kernel/debug/qat_4xxx_${device}/fw_counters | grep "Requests \[AE  ${i}\]" | awk -F':' '{print $2}' | awk '{print $1}' | tr '\n' '\t\t'
   done
   echo ""
   done
   echo -n ""
   sleep 1
   clear
 done
}

function startTelemetry(){
 enableTelemetry
 RESULTS=${OUTPUT}/Telemetry/`date "+%Y%m%d-%H%M%S"`
 mkdir -p ${RESULTS}
 echo -e "\nTelemetry started. Results are logged in ${RESULTS}"
 for device in "${arrayDevices[@]}"; do
  echo -n "Timestamp," >> ${RESULTS}/${device}.csv
  cat /sys/devices/pci`echo ${device} | awk -F':' '{print $1":"$2}'`/${device}/telemetry/device_data | awk '{print $1","}' | xargs >> ${RESULTS}/${device}.csv
 done
 while(true); do
  for device in "${arrayDevices[@]}"; do
   echo -n `date "+%Y%m%d-%H%M%S, "` >> ${RESULTS}/${device}.csv
   cat /sys/devices/pci`echo ${device} | awk -F':' '{print $1":"$2}'`/${device}/telemetry/device_data | awk '{print $2","}' | xargs >> ${RESULTS}/${device}.csv
  done
  sleep 1
 done
}

function stopTelemetry(){
 disableTelemetry
 #processName=`echo $0 | sed 's|./||g'` > /dev/null 2>&1
 kill -9 `ps aux | grep "${0}" | grep -E -- "-l|--launch" | awk '{print $2}'` > /dev/null 2>&1
 killall -w $processName > /dev/null 2>&1
 echo -e "\nTelemetry stopped"
}

function telemetry(){
 readDevices
 if [ ${LAUNCH} == false ] && [ ${STOP} == false ]; then
  echo -e '\nYou need to specify either launch [-l] or stop [-s] for using telemetry\n'
  displayHelp
 fi
 if [ ${LAUNCH} == true ] && [ ${STOP} == true ]; then
  echo -e '\nYou can only select one option from launch [-l] or stop [-s] for using telemetry\n'
  displayHelp
 fi
 if [ -z "${OUTPUT}" ] && [ ${STOP} == false ]; then
  echo -e "\nOutput directory not specified. Logs will be stored in /tmp\n"
  OUTPUT="/tmp"
 fi
 if [ ${LAUNCH} == true ]; then
  startTelemetry &
 elif [ ${STOP} == true ]; then
  stopTelemetry
 fi
}

function readDevices(){
 #arrayDevices=(`adf_ctl status | grep "qat_dev" | awk '{print $10}' | tr ',' ' ' | xargs`)
 arrayDevices=(`adf_ctl status | grep "qat_dev" | awk '{ if($16 == "up") { print $10 } }' | tr ',' ' ' | xargs`)
}

function enableTelemetry(){
 for device in "${arrayDevices[@]}"; do
  echo 1 > /sys/devices/pci`echo ${device} | awk -F':' '{print $1":"$2}'`/${device}/telemetry/control
  echo -n "Device ${device} telemetry: "
  cat /sys/devices/pci`echo ${device} | awk -F':' '{print $1":"$2}'`/${device}/telemetry/control
 done
}

function disableTelemetry(){
 for device in "${arrayDevices[@]}"; do
  echo 0 > /sys/devices/pci`echo ${device} | awk -F':' '{print $1":"$2}'`/${device}/telemetry/control
  echo -n "Device ${device} telemetry: "
  cat /sys/devices/pci`echo ${device} | awk -F':' '{print $1":"$2}'`/${device}/telemetry/control
 done
}


function main(){
 handleArgs $@
}

main $@
