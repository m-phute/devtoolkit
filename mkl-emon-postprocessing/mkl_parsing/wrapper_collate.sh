#!/bin/bash

python collate_mkl_bs1.py /mnt/madhuri/wl_analysis/tf_ssdMobilenet_v1/tf-2.2-docker/logs/mkl/iter1/results/fp32-bs1/
wait
sleep 3

python collate_mkl_bs1.py /mnt/madhuri/wl_analysis/tf_ssdMobilenet_v1/tf-2.2-docker/logs/mkl/iter1/results/int8-bs1/
wait
sleep 3

python collate_mkl_bs1.py /mnt/madhuri/wl_analysis/tf_ssdMobilenet_v1/tf-2.2-docker/logs/mkl/iter2/results/fp32-bs1/
wait
sleep 3

python collate_mkl_bs1.py /mnt/madhuri/wl_analysis/tf_ssdMobilenet_v1/tf-2.2-docker/logs/mkl/iter2/results/int8-bs1/
wait
sleep 3

python collate_mkl_bs1.py /mnt/madhuri/wl_analysis/tf_ssdMobilenet_v1/tf-2.2-docker/logs/mkl/iter3/results/fp32-bs1/
wait
sleep 3

python collate_mkl_bs1.py /mnt/madhuri/wl_analysis/tf_ssdMobilenet_v1/tf-2.2-docker/logs/mkl/iter3/results/int8-bs1/
wait
sleep 3
