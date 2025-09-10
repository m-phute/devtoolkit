#!/bin/bash


######################################
############# USER INPUT #############
######################################
#STEP 1
ip_address=localhost  #10.219.107.211 #Only one IP that maps to the DUT such as 172.16.1.1
_time=10
clients=1
portbase=443
cipher=RSA ## ECDHE-RSA-AES128-GCM-SHA256 ## TLS_AES_128_GCM_SHA256 ## ECDSA ## ECDHE-RSA-AES128-GCM-SHA256
OPENSSL_DIR=/usr/bin/
######################################
############# USER INPUT #############
######################################

#Check for OpenSSL Directory
if [ ! -d $OPENSSL_DIR ];
then
    printf "\n$OPENSSL_DIR does not exist.\n\n"
    printf "Please modify the OPENSSL_DIR variable in the User Input section!\n\n"
    exit 0
fi

helpAndError () {
    printf " ex.) ./connection.sh --servers 1 --cipher AES128-GCM-SHA256 --clients 2000 --time 30\n\n"
    exit 0
}

#Check for h flag or no command line args
if [[ $1 == *"h"* ]]; then
    helpAndError
    exit 0
fi

#Check for emulation flag
if [[ $@ == **emulation** ]]
then
    emulation=1
fi

#cmd1 is the first part of the commandline and cmd2 is the second partrt
#The total commandline will be cmd1 + "ip_address:port" + cmd2
cmd1="$OPENSSL_DIR/openssl s_time -connect"
if [[ $cipher =~ "TLS" ]];
then
	cmd2="-new -ciphersuites $cipher  -time $_time "
else
	cmd2="-new -cipher $cipher  -time $_time "
fi
#Print out variables to check
printf "\n Location of OpenSSL:           $OPENSSL_DIR\n"
printf " IP Addresses:                  $ip_address\n"
printf " Time:                          $_time\n"
printf " Clients:                       $clients\n"
printf " Port Base:                     $portbase\n"
printf " Cipher:                        $cipher\n\n"

#read

#Remove previous .test files
rm -rf ./.test_*

#Get starttime
starttime=$(date +%s)

#Kick off the tests after checking for emulation
if [[ $emulation -eq 1 ]]
then
    for (( i = 0; i < ${clients}; i++ )); do
        printf "$cmd1 $ip_address:$(($portbase)) $cmd2 > .test_$(($portbase))_$i &\n"
    done
    exit 0
else
    for (( i = 0; i < ${clients}; i++ )); do
        $cmd1 $ip_address:$(($portbase)) $cmd2 > .test_$(($portbase))_$i &
    done
fi

waitstarttime=$(date +%s)
# wait until all processes complete
while [ $(ps -ef | grep "openssl s_time" | wc -l) != 1 ];
do
    sleep 1
done

total=$(cat ./.test_$(($portbase))* | awk '(/^[0-9]* connections in [0-9]* real/){ total += $1/$4 } END {print total}')
echo $total >> .test_sum
sumTotal=$(cat .test_sum | awk '{total += $1 } END { print total }')
printf "Connections per second:      $sumTotal CPS\n"
printf "Finished in %d seconds (%d seconds waiting for procs to start)\n" $(($(date +%s) - $starttime)) $(($waitstarttime - $starttime))
rm -rf ./.test_*
