#!/bin/bash

# inputs: 1.cipher 2.qat_mode 3.nginx_processes 4.num_clients 5.iterations 6.logdir

cipher=$1    ## rsa4k_x448 rsa2k_x25519 rsa2k_p256 ecdsaP256_ecdheX25519
qat_mode=$2    ## qathw / qatsw / sw
nginx_processes=$3
num_clients=$4
num_iter=$5
logdir=$6

#logdir=$(pwd)/logs_nginx_$(date +%Y%m%d%H%M%S)
#mkdir -p ${logdir}

## Check QAT mode validity
if [ "${qat_mode}" == "qathw" ]; then
  NGINX_PATH=/home/qat/nginx/nginx_qat_hw
  conf_param="QAThw"

elif [ "${qat_mode}" == "qatsw" ]; then
  NGINX_PATH=/home/qat/nginx/nginx_qat_sw
  conf_param="QATsw"

elif [ "${qat_mode}" == "sw" ]; then
  NGINX_PATH=/home/qat/nginx/nginx_qat_sw
  conf_param="noQAT"

else
  echo ${qat_mode} not a valid mode. Please choose from qathw, qatsw, or sw
  exit 1
fi

## Check if nginx path exists
if [ -z ${NGINX_PATH} ]; then
  echo Nginx path ${NGINX_PATH} not found. Please install Nginx at this location and rerun...
  exit 1
fi

## Check if conf files found for cipher
if [ -z ${NGINX_PATH}/conf/${cipher} ]; then
  echo Conf files for cipher ${cipher} not found. Please keep nginx conf files for this cipher at this location and rerun...
  exit 1
fi


## Start NGINX
NGINX_CONF_FILE="nginx.${conf_param}_${cipher}_p$((nginx_processes)).conf"

pushd ${NGINX_PATH}

if (( $(ps aux | grep sbin/nginx | wc -l) > 1 )); then
  ./sbin/nginx -c ./conf/${cipher}/${NGINX_CONF_FILE} -s stop
  sleep 2
fi

numactl -C 1-$((0 + nginx_processes/2)),121-$((120 + nginx_processes/2)) -m 0 ./sbin/nginx -c ./conf/${cipher}/${NGINX_CONF_FILE}
sleep 1
ps aux | grep nginx | wc -l

popd

if (( $(ps aux | grep nginx | wc -l) <= 4 )); then
  echo Nginx not started correctly. Please check and rerun...
  #exit 1
fi


## Number of client systems to use
if (( ${num_clients} <= 1000 )); then
  client_machines=1
  clients_per_machine=${num_clients}

elif (( ${num_clients} > 1000 )) && (( ${num_clients} <= 2000 )); then
  client_machines=2
  clients_per_machine=$(( $num_clients/2 ))

else
  client_machines=3
  clients_per_machine=$(( $num_clients/3 ))
fi


## Run Connection Test
for run in `seq 1 $num_iter`; do
  cmd=""

  for machine in `seq 1 $client_machines`; do
    cmd+="ssh root@c${machine} \"cd /home/mphute/client/scripts; ./wrapper_connection.sh $clients_per_machine \" & "
  done

  logname=${cipher}_${qat_mode}_${nginx_processes}processes_${num_clients}clients_iter${run}.log

  echo $cmd
  eval $cmd 2>&1 | tee ${logdir}/${logname}
  wait
  sleep 2

  cps=$( grep "Connections per second:" ${logdir}/${logname} | awk '{print $4; SUM += $4} END {print SUM}' )

  echo "${cipher},${qat_mode},${nginx_processes},${num_clients},${run},${cps}" >> ${logdir}/results.csv

done
