#!/bin/bash

# ./qatzip_test.sh 1 8

QATZIP_TESTS=$1  ## Needed when LIMIT_DEV_ACCESS=1
QATZIP_THREADS=$2  ## Should be <= QAT processes in conf file

QATZIP_PATH=/home/qat/qatzip/qatzip-master/

logdir=$(pwd)/logs_qatzip_$(date +%Y%m%d%H%M%S)
mkdir -p ${logdir}

for direction in comp; do   # comp decomp
  for level in 1; do   # 1 9
    for chunk in 8192; do   # 8192 65536
      echo "-------------------------------------"
      echo "Starting ${QATZIP_TESTS} QATzip processes with"
      echo "QATzip parameters:"
      echo "Threads: ${QATZIP_THREADS}"
      echo "Direction: ${direction}"
      echo "Level: ${level}"
      echo "Chunk: ${chunk}"
      echo "-------------------------------------"

      cmd=""

      if [[ "${QATZIP_TESTS}" == "1" ]]; then
        cmd+="${QATZIP_PATH}/test/test -m 4 -l 1000 -t ${QATZIP_THREADS} -B 0 -D ${direction} -L ${level} -i ${QATZIP_PATH}/calgary -T dynamic -C ${chunk} 2>&1 | tee ${logdir}/${direction}_${level}_${chunk}_${QATZIP_TESTS}tests_${QATZIP_THREADS}threads.log"

      else
        for i in `seq 1 $((QATZIP_TESTS/2))`; do
          cmd+="numactl -C 0-59,120-179 -m 0 ${QATZIP_PATH}/test/test -m 4 -l 1000 -t ${QATZIP_THREADS} -B 0 -D ${direction} -L ${level} -i ${QATZIP_PATH}/calgary -T dynamic -C ${chunk} 2>&1 | tee -a ${logdir}/${direction}_${level}_${chunk}_${QATZIP_TESTS}tests_${QATZIP_THREADS}threads.log & "
	done

	for i in `seq $((QATZIP_TESTS/2 + 1)) ${QATZIP_TESTS}`; do
          cmd+="numactl -C 60-119,180-239 -m 1 ${QATZIP_PATH}/test/test -m 4 -l 1000 -t ${QATZIP_THREADS} -B 0 -D ${direction} -L ${level} -i ${QATZIP_PATH}/calgary -T dynamic -C ${chunk} 2>&1 | tee -a ${logdir}/${direction}_${level}_${chunk}_${QATZIP_TESTS}tests_${QATZIP_THREADS}threads.log & "
	done
      fi

      #echo $cmd
      eval $cmd

      wait
      sleep 2

      echo "Done runnning QATzip processes"
      echo "-------------------------------------"
      echo -n "Total Throughput: "
      awk '{sum+=$8;} END{print sum;}' ${logdir}/${direction}_${level}_${chunk}_${QATZIP_TESTS}tests_${QATZIP_THREADS}threads.log

      echo -n "Compression Ratio: "
      awk '{print $12}' ${logdir}/${direction}_${level}_${chunk}_${QATZIP_TESTS}tests_${QATZIP_THREADS}threads.log | cut -d '=' -f 2 | cut -d '%' -f 1 | awk '{sum += $1} END {print sum/(NR * 100)}'

    done
  done
done
