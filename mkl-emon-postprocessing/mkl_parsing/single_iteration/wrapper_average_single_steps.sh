#!/bin/bash

# usage: ./wrapper_average_single_iteration.sh </path/to/logs/*_single_iteration> <num_lines_in_iteration>

topdir=$1
start_num=0
end_num=49
line_check=$2

if [[ "${topdir: -1}" != "/" ]]; then
	topdirname=$(echo ${topdir} | rev | cut -d'/' -f1 | rev)
else
	topdirname=$(echo ${topdir} | rev | cut -d'/' -f2 | rev)
fi
#echo topdirname ${topdirname}

for configdir in ${topdir}/*; do

	configdirname=topdirname=$(echo ${topdir} | rev | cut -d'/' -f1 | rev)

	for folder in ${configdir}/*; do

		foldername=$(echo ${folder} | rev | cut -d'/' -f1 | rev)
		#echo foldername ${foldername}

		if [[ "${foldername}" != "${configdirname}_single_iteration" ]]; then
			echo processing ${foldername}
			python average_single_steps.py -d ${folder} -s ${start_num} -e ${end_num} -c ${line_check}
			wait
			sleep 2
		fi
	done
done
