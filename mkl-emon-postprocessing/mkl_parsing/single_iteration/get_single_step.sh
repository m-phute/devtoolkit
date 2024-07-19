#!/bin/bash

# usage: ./get_single_dtep.sh </path/to/individual_mkl_config_dir> <num_iterations> <lines_per_iteration>

##### Lines per iteration #####
# TF RN50-v1.5 FP32  : 61
# TF RN50-v1.5 INT8  : 57
# MX Bert Base FP32  : 148
# MX Bert Base INT8  : 197
# TF SSD MN v1 BS 1  : 71
# TF WnD FP32 BS 1   : 12
# TF WnD FP32 BS 512 : 266
# TF WnD INT8 BS 1   : 14
# TF WnD INT8 BS 512 : 268


topdir=$1
num_iter=$2
iter_lines=$3

# number of lines = number_of_iterations * lines_per_iteration
num_lines=$((num_iter * iter_lines))
echo num_lines ${num_lines}

# get foldername and create single_iteration directory
if [[ "${topdir: -1}" != "/" ]]; then
	foldername=$(echo ${topdir} | rev | cut -d'/' -f1 | rev)
else
	foldername=$(echo ${topdir} | rev | cut -d'/' -f2 | rev)
fi
logdir=${topdir}/${foldername}_singleIter
mkdir -p ${logdir}

for file in ${topdir}/*; do

	#echo file ${file}

	filename=$(echo ${file} | cut -d'.' -f1 | rev | cut -d'/' -f1 | rev)

	if [[ "${filename}" != "${foldername}_singleIter" ]]; then

		#echo filename ${filename}

		# create a folder to store the single iteration logs
		mkdir -p ${logdir}/${filename}

		# get mkl lines from log
		grep "dnnl_verbose\|mkldnn_verbose\|MKL_VERBOSE" ${file} >> ${topdir}/temp_mkl_lines.log

		# get last 'num_lines' lines
		tail -${num_lines} ${topdir}/temp_mkl_lines.log >> ${topdir}/temp_iter_lines.log

		# split it into individual logs
		split -l ${iter_lines} -d -a 3 --additional-suffix=.log ${topdir}/temp_iter_lines.log ${logdir}/${filename}/${filename}_

		# remove the temp files
		rm ${topdir}/temp_mkl_lines.log ${topdir}/temp_iter_lines.log
	fi
done

