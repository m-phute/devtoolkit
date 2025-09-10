# Nginx + OpenSSL Setup And Run BKM

## Nginx Server Setup

### Install Nginx & OpenSSL
`dnf install nginx openssl`
<br><br>

### Edit Nginx Config File

#### Increase Maximum Open Files Limit

Change it to a very large number. Set it to 'unlimited' if the OS allows <br>
`ulimit -n 1000000000`
<br>

#### Uncomment Nginx Conf File Settings for a TLS Enabled Server
See the Nginx conf file for details <br>
`vim /etc/nginx/nginx.conf`
<br>

#### Change Number of Worker Connections
* Nginx automatically sets `worker_processes = number_of_cpus`. Set the value to the number of CPUs you want to pin the Nginx server to.
* Change `worker_connections` to a larger value as needed.
* Total connections supported by nginx server is `worker_connections * worker_processes`
<br><br>

### Generate Certificate and Key
Below key is generated with RSA-2K encryption <br>
`mkdir -p /etc/pki/nginx/private` <br>
`openssl req -x509 -nodes -newkey rsa:2048 -keyout /etc/pki/nginx /server.key -out /etc/pki/nginx /server.crt`
<br><br><br>

## OpenSSL Clients Setup

### Copy connections.sh Script
Copy the connections.sh script to the working directory <br>
`cp connections.sh /home`
<br><br>

### Edit connections.sh
Edit the fields in the "USER INPUT" section at the beginning of the script to match the setup and test requirements
<br><br><br>

## Running The Workload

### Start Nginx Server
`numactl -C <core_range> -m <numa_to_pin> nginx` <br>
Confirm whether all instances have started. Below command should output `#instances + 2` <br>
`ps aux | grep nginx | wc -l` <br>
<br><br>

### Run Connections Test
In the client, run the connections.sh script. <br>
`bash connections.sh` <br><br>

The output will show the runtime parameters and the connections per second achieved by the clients. <br>
```
Location of OpenSSL:           /usr/bin/
IP Addresses:                  localhost
Time:                          10
Clients:                       1
Port Base:                     443
Cipher:                        RSA

Connections per second:      204.455 CPS
Finished in 11 seconds (0 seconds waiting for procs to start)
```
