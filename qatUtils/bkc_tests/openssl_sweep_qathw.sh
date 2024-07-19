#!/bin/bash

ASYNC=112
SEC=10
NUM_INSTANCES=2
NUM_PROCESSES=32
MULTI=${NUM_PROCESSES}

logdir=$(pwd)/logs_openssl_$(date +%Y%m%d%H%M%S)
mkdir -p ${logdir}

function run_sym(){

  /home/qat/qatUtils/qat-utils.sh  -config --dev-acces 0 --section-name SHIM --services-enabled sym --processes ${NUM_PROCESSES} --cy-instances ${NUM_INSTANCES}

  for ALG in ChaCha20-Poly1305 id-aes128-GCM id-aes256-GCM sha3-224 sha3-256; do
    for BYTES in "4096" "16384"; do
      /usr/local/ssl_111m_hw/bin/openssl speed -engine qatengine -seconds ${SEC} -bytes ${BYTES} -multi ${MULTI} -async_jobs ${ASYNC} -evp ${ALG} 2>&1 | tee ${logdir}/openssl-speed_${ALG}_${ASYNC}ajobs_${BYTES}bytes_${MULTI}multi.log
      wait
      sleep 1
    done
  done

  for ALG in aes-128-cbc-hmac-sha1 aes-128-cbc-hmac-sha256 aes-256-cbc-hmac-sha1 aes-256-cbc-hmac-sha256; do
    for BYTES in "4096" "8192"; do
      /usr/local/ssl_111m_hw/bin/openssl speed -engine qatengine -seconds ${SEC} -bytes ${BYTES} -multi ${MULTI} -async_jobs ${ASYNC} -evp ${ALG} 2>&1 | tee ${logdir}/openssl-speed_${ALG}_${ASYNC}ajobs_${BYTES}bytes_${MULTI}multi.log
      wait
      sleep 1
    done
  done  

}


function run_asym(){

  /home/qat/qatUtils/qat-utils.sh  -config --dev-acces 0 --section-name SHIM --services-enabled asym --processes ${NUM_PROCESSES} --cy-instances ${NUM_INSTANCES}

  for ALG in rsa2048 rsa3072 ecdhp224 ecdhp256 ecdhp384 ecdhp521 ecdhx25519 ecdhx448 ecdsap224 ecdsap256 ecdsap384 ecdsap521; do
    /usr/local/ssl_111m_hw/bin/openssl speed -engine qatengine -seconds ${SEC} -multi ${MULTI} -async_jobs ${ASYNC} ${ALG} 2>&1 | tee ${logdir}/openssl-speed_${ALG}_${ASYNC}ajobs_${MULTI}multi.log
    wait
    sleep 1
  done

}

#run_sym
run_asym
