#!/bin/bash

INPUT=nginx_tests.csv

logdir=$(pwd)/logs_nginx_$(date +%Y%m%d%H%M%S)
mkdir -p ${logdir}
echo "cipher,qat_mode,nginx_processes,num_clients,run,cps" >> ${logdir}/results.csv

OLDIFS=$IFS
IFS=','

[ ! -f $INPUT ] && { echo "$INPUT file not found"; exit 1; }

while read cipher mode processes clients runs; do

  if [ "$cipher" == "" ] | [ "$mode" == "" ] | [ "$processes" == "" ] | [ "$clients" == "" ] | [ "$runs" == "" ]; then
    echo Some field is missing. Please check the $INPUT file...
    exit 1

  else
    echo cipher-$cipher mode-$mode processes-$processes clients-$clients runs-$runs
  fi
  
  cmd="./nginx_connection_test.sh $cipher $mode $processes $clients $runs $logdir"
  #echo $cmd
  eval $cmd
  
  wait
  sleep 5

done < $INPUT

IFS=$OLDIFS
