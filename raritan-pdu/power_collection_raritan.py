# Script to collect wall power using Raritan PDU while running workload on the SUT
# For details/changes please contact Madhuri Phute (madhuri.phute@intel.com)

import time
import os
import re
import paramiko
import sys
import multiprocessing
import pandas
from datetime import datetime
from raritan.rpc import Agent, pdumodel, firmware

# SUT details
sut_ip = "10.242.51.50"
sut_user = "root"
sut_pw = "dcso@123"

# PDU details
OUTLET = 6
pdu_ip = "10.242.51.43"
pdu_user = "Operator"
pdu_pw = "intel@123"

# Connect to PDU
agent = Agent("https", pdu_ip, pdu_user, pdu_pw, disable_certificate_verification=True)
pdu = pdumodel.Pdu("/model/pdu/0", agent)
firmware_proxy = firmware.Firmware("/firmware", agent)
outlets = pdu.getOutlets()
outlet = outlets[OUTLET-1]
outlet_sensors = outlet.getSensors()


def run_cmd(sut_ip, sut_user, sut_pw, cmd):
    ret = None
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(sut_ip, username=sut_user, password=sut_pw, timeout=300)
        _, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
        output = str(ssh_stdout.read().decode('utf-8'))
        error = str(ssh_stderr.read().decode('utf-8'))
        ret = (ssh_stdout.channel.recv_exit_status(), output + error)
        
        # for line in iter(ssh_stdout.readline, ""):
            # if line == "":
                # break
            # else:
                # print(line, end="")
        
    except Exception as e:
        print("ERROR: Failed to run command")
        print(e)
        try:
            print(e.errors())
        except:
            pass
        return
    try:
        ssh.close()
    except:
        pass
    return ret
    
    
def collect_active_power(stop_power, tag, log_path):
    print("Starting power measurement with testName {}".format(tag))
    measured_power=pandas.DataFrame(columns=['Timestamp', 'Active Power'])
    
    while not stop_power.is_set():
        # Get Time
        current_datetime = datetime.now()
        time_stamp = current_datetime.strftime("%Y%m%d%H%M%S")
        
        # Get Power
        sensor_reading = outlet_sensors.activePower.getReading()
        power_reading = sensor_reading.value
        
        # Add to DataFrame
        row_to_add = {'Timestamp': time_stamp, 'Active Power': power_reading}
        measured_power = measured_power.append(row_to_add, ignore_index=True)
    
    # Write to Excel file
    filename = f'{log_path}\{tag}.xlsx'
    writer = pandas.ExcelWriter(filename)
    measured_power.to_excel(writer)
    writer.save()
    print(f'Data stored at {filename}')


def run_on_sut(stop_power, cmd):
    try:
        print("Running command " + cmd)
        retcode, output = run_cmd(sut_ip, sut_user, sut_pw, cmd)
        print(output)
        stop_power.set()
    except Exception as e:
        print(e)
        return False
  
  
def run_together(stop_power, cmd, tag, log_path,):

    power_process = multiprocessing.Process(target = collect_active_power, args = (stop_power, tag, log_path,))
    sut_process = multiprocessing.Process(target = run_on_sut, args = (stop_power, cmd,))
    
    power_process.start()
    sut_process.start()
    
    power_process.join()
    sut_process.join()
                
    print("Done")

def ai_power_collect():

    run_tf = False
    run_pt = True

    tf_topologies = ["resnet50v1_5", "ssd-resnet34", "bert_large", "transformer_mlperf", "dien", "3d_unet_mlperf"]
    pt_topologies = ["bert_large", "dlrm", "ssd_rn34", "distilbert_base", "rnn_t", "maskrcnn"]  # ["resnet50_v15", "bert_large", "dlrm", "resnext101_32x16d", "ssd_rn34", "distilbert_base", "rnn_t", "maskrcnn"]
    precisions = ["amx_int8", "amx_bfloat16", "amx_bfloat32", "avx_int8", "avx_fp32"]
    modes = ["throughput"]  #["latency", "throughput"]
    
    # Directory to store logs
    logdate = datetime.now()
    logdate_str = logdate.strftime("%Y%m%d%H%M%S")
    log_path = f'C:\\Users\\lab_uhsusr\\Documents\\Raritan\\logs_{logdate_str}'
    os.makedirs(log_path)
    
    stop_power = multiprocessing.Event()

    if run_tf:
        for topology in tf_topologies:
            for precision in precisions:
                for mode in modes:
                
                    real_dataset = ["bert_large", "dien", "transformer_mlperf"]
                    if topology in real_dataset:
                        data_type = "real"
                    else:
                        data_type = "dummy"
                
                    cmd = f"cd /home/mphute/pnpwls/ai && python run_tf_inference.py -t {topology} -p {precision} -m {mode} -d {data_type} -g oobPowerCheckoutTF -e 1"
                    # cmd = f"cd /home/mphute && ./timer_script.sh 5"
                    tag = f"oobPowerCheckoutTF_{topology}_{precision}_{mode}"
                    # tag = "demo_run"
                    run_together(stop_power, cmd, tag, log_path,)
                
                    stop_power.clear()
    
    if run_pt:
        for topology in pt_topologies:
            for precision in precisions:
                
                # Unsupported topology-precision combinations
                if topology == "maskrcnn" or topology == "rnn_t":
                    if precision == "amx_int8" or precision == "avx_int8":
                        print(f"Skipping combination {topology} {precision}")
                        continue
                
                for mode in modes:
                
                    real_dataset = ["bert_large", "dlrm", "maskrcnn", "rnn_t", "ssd_rn34", "distilbert_base"]
                    if topology in real_dataset:
                        data_type = "real"
                    else:
                        data_type = "dummy"
                
                    cmd = f"cd /home/mphute/pnpwls/ai && python run_pt_inference.py -t {topology} -p {precision} -m {mode} -d {data_type} -g oobPowerCheckoutPT -e 1"
                    # cmd = f"cd /home/mphute && ./timer_script.sh 5"
                    tag = f"oobPowerCheckoutPT_{topology}_{precision}_{mode}"
                    # tag = "demo_run"
                    run_together(stop_power, cmd, tag, log_path,)
                
                    stop_power.clear()

load_time = datetime.now()
print(f"power_collection_raritan.py loaded successfully at {load_time}")