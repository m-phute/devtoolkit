#!/bin/bash

logdir=$(pwd)/logs_cpa_$(date +%Y%m%d%H%M%S)
mkdir -p ${logdir}

NUM_INSTANCES=1
NUM_PROCESSES=64

function run_sym() {

  LIMIT_DEV_ACCESS=0 SECTION_NAME=SSL SERVICES_ENABLED=sym CY_INSTANCES=${NUM_INSTANCES} DC_INSTANCES=0 PROCESSES=${NUM_PROCESSES} /home/qat/qat-invoke.sh
  wait
  sleep 2
  /home/qat/cpa_sample_code/QAT20.L.0.9.0-00023/quad/cpa_sample_code runTests=1 2>&1 | tee ${logdir}/sym.log
  wait
  sleep 2
}


function run_rsa() {
  
  LIMIT_DEV_ACCESS=0 SECTION_NAME=SSL SERVICES_ENABLED=asym CY_INSTANCES=${NUM_INSTANCES} DC_INSTANCES=0 PROCESSES=${NUM_PROCESSES} /home/qat/qat-invoke.sh
  wait
  sleep 2
  /home/qat/cpa_sample_code/QAT20.L.0.9.0-00023/quad/cpa_sample_code runTests=2 2>&1 | tee ${logdir}/rsa.log
  wait
  sleep 2
}


function run_ecdsa() {

  LIMIT_DEV_ACCESS=0 SECTION_NAME=SSL SERVICES_ENABLED=asym CY_INSTANCES=${NUM_INSTANCES} DC_INSTANCES=0 PROCESSES=${NUM_PROCESSES} /home/qat/qat-invoke.sh
  wait
  sleep 2
  /home/qat/cpa_sample_code/QAT20.L.0.9.0-00023/quad/cpa_sample_code runTests=8 2>&1 | tee ${logdir}/ecdsa.log
  wait
  sleep 2
}


function run_dh() {
  
  LIMIT_DEV_ACCESS=0 SECTION_NAME=SSL SERVICES_ENABLED=asym CY_INSTANCES=${NUM_INSTANCES} DC_INSTANCES=0 PROCESSES=${NUM_PROCESSES} /home/qat/qat-invoke.sh
  wait
  sleep 2
  /home/qat/cpa_sample_code/QAT20.L.0.9.0-00023/quad/cpa_sample_code runTests=16 2>&1 | tee ${logdir}/dh.log
  wait
  sleep 2
}


function run_dc() {

  LIMIT_DEV_ACCESS=0 SECTION_NAME=SSL SERVICES_ENABLED=dc CY_INSTANCES=0 DC_INSTANCES=${NUM_INSTANCES} PROCESSES=${NUM_PROCESSES} /home/qat/qat-invoke.sh
  wait
  sleep 2
  /home/qat/cpa_sample_code/QAT20.L.0.9.0-00023/quad/cpa_sample_code runTests=32 2>&1 | tee ${logdir}/dc.log
  wait
  sleep 2
}

#run_sym
#run_rsa
#run_ecdsa
#run_dh
run_dc
