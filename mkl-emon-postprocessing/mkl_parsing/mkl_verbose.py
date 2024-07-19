'''
usage:
    For CLX runs:
    python mkl_verbose.py -d /root/sbhatt3/DNNL_Verbose/Logs/wnd_test_logs/

    For Rome runs:
    python mkl_verbose.py -d /root/sbhatt3/DNNL_Verbose/Logs/wnd_rome_logs/ -r

    For SingleIter runs for CLX data:
    python mkl_verbose.py -d /root/sbhatt3/DNNL_Verbose/Logs/wnd_test_logs/ -s

    For SingleIter runs for Rome data:
    python mkl_verbose.py -d /root/sbhatt3/DNNL_Verbose/Logs/wnd_rome_logs/ -r -s

'''


import os
import sys
from glob import glob
import subprocess
import re
import pandas as pd
import multiprocessing
from multiprocessing import Pool
import xlsxwriter
from datetime import datetime
from dateutil import parser
import traceback
import math
import getopt

# threads to use for parallel processing
parallel_processes = 36

# user configs to change

# top directory of MKL data where it will search
#logname = sys.argv[1]
#topdir = logname.rsplit('/', 1)[0]
#resultdir = sys.argv[2]
#topdir = sys.argv[1]
topdir = ""
isSingleIter = False
isRome = False
machine = "SPR"
default_freq = 0 #2.1 # AVX3 all core turbo. Will use this number if not in core freq list below from EMON


try:
    opts, args = getopt.getopt(sys.argv[1:],"hd:rf:s",["dir=","freq="])
except getopt.GetoptError:
      print('mkl_parsing.py -d <directory> -r')
      sys.exit(2)
for opt, arg in opts:
  if opt == '-h':
     print('mkl_parsing.py -d <directory> -r')
     sys.exit()
  elif opt in ("-d", "--dir"):
     topdir = arg
  elif opt in ("-s", "--single_iter"):
     isSingleIter = True
     print("Single Iter processing turned on")
  elif opt in ("-r", "--rome"):
     isRome = True
     machine = "Rome"
     print("Rome machine")
  elif opt in ("-f", "--freq"):
     default_freq = arg


resultdir = topdir
#print("log being processed: " + logname)
print("topdir" + topdir)


# Get list of verbose and non-verbose times from csv

if not isSingleIter:
    try:
        nonVerbose_csv = pd.read_csv(topdir + "/../timing_nonVerbose.csv")
    except:
        print("WARNING: timing_nonVerbose.csv file not found")
    try:
        verbose_csv = pd.read_csv(topdir + "/../timing_verbose.csv")
    except:
        print("WARNING: timing_verbose.csv file not found")
else:
    try:
        nonVerbose_csv = pd.read_csv(topdir + "/mnt/madhuri/wl_analysis/re_process/all_mkl/timing_nonVerbose_singleIter.csv")
    except:
        print("WARNING: timing_nonVerbose.csv file not found")
    try:
        verbose_csv = pd.read_csv(topdir + "/mnt/madhuri/wl_analysis/re_process/all_mkl/timing_verbose_singleIter.csv")
    except:
        print("WARNING: timing_verbose.csv file not found")

try:
    cpuFreq_csv = pd.read_csv(topdir + "/../edp_freq.csv")
except:
    print("WARNING: edp_freq.csv file not found")

df_nonVerbose = pd.DataFrame(columns=['Config', 'Time'])
df_verbose = pd.DataFrame(columns=['Config', 'Time'])
df_cpuFreq = pd.DataFrame(columns=['Config', 'Frequency'])

try: 
    for idx, row in nonVerbose_csv.iterrows():
        #row['Config'] = row['Config'].split('/')[-1].split('_')[0] + '-' + row['Config'].split('/')[-1].split('_')[-1].split('.')[0]
        row['Config'] = row['Config'].split('/')[-1].split('.')[0]
        df_nonVerbose = df_nonVerbose.append(row)
except:
    print("WARNING: Skipping nonVerbose timing information")

try:
    for idx, row in verbose_csv.iterrows():
        #row['Config'] = row['Config'].split('/')[-1].split('_')[0] + '-' + row['Config'].split('/')[-1].split('_')[-1].split('.')[0]
        row['Config'] = row['Config'].split('/')[-1].split('.')[0]
        df_verbose = df_verbose.append(row)
except:
    print("WARNING: Skipping verbose timing information")

try :
    for idx, row in cpuFreq_csv.iterrows():
        #row['Config'] = row['Config'].split('/')[-1].split('_')[-1].split('.')[0]
        #print(row)
        df_cpuFreq = df_cpuFreq.append(row)
except:
    print("WARNING: Skipping frequency information")

non_verbose_times = dict(zip(df_nonVerbose.Config, df_nonVerbose.Time))
verbose_times = dict(zip(df_verbose.Config, df_verbose.Time))
cpu_freqs = dict(zip(df_cpuFreq.Config, df_cpuFreq.Frequency))


workload_list = []
ratio_bins = [0.125, 0.25, 0.5, 1, 2, 4, 8]
regex = re.compile(r'mb(?P<mb>[0-9]+)*_ic(?P<ic>[0-9]+)*oc(?P<oc>[0-9]+)*_ih(?P<ih>[0-9]+)*oh(?P<oh>[0-9]+)*kh(?P<kh>[0-9]+)*sh(?P<sh>[0-9]+)*dh(?P<dh>[0-9]+)*ph(?P<ph>[0-9]+)*_iw(?P<iw>[0-9]+)*ow(?P<ow>[0-9]+)*kw(?P<kw>[0-9]+)*sw(?P<sw>[0-9]+)*dw(?P<dw>[0-9]+)*pw(?P<pw>[0-9]+)*')
regex_g = re.compile(r'mb(?P<mb>[0-9]+)*_g(?P<g>[0-9]+)*ic(?P<ic>[0-9]+)*oc(?P<oc>[0-9]+)*_ih(?P<ih>[0-9]+)*oh(?P<oh>[0-9]+)*kh(?P<kh>[0-9]+)*sh(?P<sh>[0-9]+)*dh(?P<dh>[0-9]+)*ph(?P<ph>[0-9]+)*_iw(?P<iw>[0-9]+)*ow(?P<ow>[0-9]+)*kw(?P<kw>[0-9]+)*sw(?P<sw>[0-9]+)*dw(?P<dw>[0-9]+)*pw(?P<pw>[0-9]+)*')
regex_gemm = re.compile(r'mb(?P<mb>[0-9]+)*ic(?P<ic>[0-9]+)*oc(?P<oc>[0-9]+)*')

#print("Regex" + str(regex))
#print("Regex_g" + str(regex_g))

manager = multiprocessing.Manager()
all_primitives = manager.list()
all_kernels_time = manager.list()
all_kernels_eff = manager.list()
all_timings = manager.list()
all_tmul_speedups = manager.list()

def process_workloads(workload_info):
  workload = workload_info['workload']
  #workload = topdir.split('/')[-1].split('_')[0] + '-' + logname.rsplit('_',1)[1].split('.')[0]
  print("workload " + workload)
  precision = workload_info['precision']
  #precision = topdir.split('/')[-1].split('_')[0].split('-')[2]
  isMixedPrecision = False #used only for MKLDNN GEMMs
  print("precision " + precision)
  log = workload_info['log']
  print("log " + log)
  #log = logname
  #namespace_dir = workload_info['dir']
  num_cores = workload_info['num_cores']



  mkl = []
  mkldnn_convolution = []
  mkldnn_non_convolution = []
  line_num = 0
  total_mkldnn_time_ms = 0
  total_mkl_time_ms = 0
  primitives = {}
  kernels = {}
  get_timestamp = -1
  workload_start = workload_end = None
  workload_config = workload #+ '_' + precision
  #workload_config_freq = workload.rsplit('-',1)[0] #+ '_' + precision
  workload_config_freq = workload.rsplit('_',1)[0] #+ '_' + precision
  print("workload config freq = " + workload_config_freq)
  freq = default_freq if workload_config_freq not in cpu_freqs or cpu_freqs[workload_config_freq] is None else cpu_freqs[workload_config_freq]
  print("freq: " + str(freq))
  if isRome:
    #Calculations below are for AVX2 implementation; AVX currently not supported
    vector_units_per_core = 2  # AVX2 units per core
    ideal_macspersec_fp32 = 8 * vector_units_per_core * num_cores * freq * 1e9 #256/32=8; this is the same for fp32 and int8 on Rome
    ideal_macspersec_int8 = ideal_macspersec_fp32
    peak_gops_fp32 = num_cores * freq * 8 * vector_units_per_core * 2 #this is the same for fp32 and int8 on Rome
    peak_gops_int8 = peak_gops_fp32
    #tmul_ideal_macspersec_percore = 0
    dram_channels = 16 if num_cores > 64 else 8  # number of dram channels available to workload
    peak_gbps = 3.2 * 8 * dram_channels  # based on dram freq
  else:
    #Calculations below are for AVX512 implementation; AVX/AVX2 on Xeon currently not supported
    vector_units_per_core = 2  # AVX512 units per core
    ideal_macspersec_fp32 = 16 * vector_units_per_core * num_cores * freq * 1e9
    ideal_macspersec_int8 = ideal_macspersec_fp32 * 4
    peak_gops_fp32 = num_cores * freq * 16 * vector_units_per_core * 2
    peak_gops_int8 = peak_gops_fp32 * 4
    #tmul_ideal_macspersec_percore = 1024 if precision == 'int8' else 68.3
    dram_channels = 12 if num_cores > 28 else 6  # number of dram channels available to workload
    peak_gbps = 2.934 * 8 * dram_channels  # based on dram freq
  #ideal_macspersec = ideal_macspersec_int8 if precision == 'int8' else ideal_macspersec_fp32
  peak_gops = peak_gops_int8 if precision == 'int8' else peak_gops_fp32 #based on WL default precision
  inflection_fp32 = peak_gops_fp32 / peak_gbps
  inflection_int8 = peak_gops_int8 / peak_gbps
  inflection = peak_gops / peak_gbps #based on WL default precision

  #print(workload, precision, log)

  #primitives['convolution'] = {}
  #primitives['convolution']['time_ms'] = 0
  #primitives['convolution']['count'] = 0
  #primitives['inner_product'] = {}
  #primitives['inner_product']['time_ms'] = 0
  #primitives['inner_product']['count'] = 0
  for line in open(log):
    #print(line)
    line_num += 1
    MKL_LINE = MKLDNN_LINE = False
    try:
      if 'Sample' in line:  # some weird text that needs to be removed
        line = re.sub(r'Sample.*MKL','MKL', line)

      if '[2020' in line:
        timestamp = re.split('\[|\]', line)[3]

      if get_timestamp == line_num:
        workload_start = parser.parse(timestamp)

      if '# Execute' in line:
        get_timestamp = line_num + 2

      elif '# Collect logs' in line:
        workload_end = parser.parse(timestamp)  # last timestamp saved
 
      elif 'MKL_VERBOSE' in line and 'Intel' not in line:
        MKL_LINE = True
        primitive = call = re.split('\(|\)', line.split()[1])[0]
        #print("primitive " + primitive)
        details = re.split('\(|\)', line.split()[1])[1]
        #print("details " + details)
        duration = line.split()[2]
        #print("duration " + duration)
        duration_num = float(re.findall('\d+\.*\d*', duration)[0])
        nthr_line = line.split()[7]
        nthr = re.split(':', nthr_line.split()[0])[1]
        #print("nthr " + nthr)
    
        if 'ms' in duration:
          duration_ms = duration_num
        elif 'us' in duration:
          duration_ms = duration_num / 1e3
        elif 'ns' in duration:
          duration_ms = duration_num / 1e6
        elif 'ps' in duration:
          duration_ms = duration_num / 1e9
        elif 's' in duration:
          duration_ms = duration_num * 1e3
        else:
          print("ERROR, unexpected duration %s for %s"%(duration, workload, precision, log))
          return False

        if duration_ms <= 0:
          #print("WARNING, found zero duration", line, workload, precision, log)
          #print("duration_ms" + str(duration_ms))
          continue

        #row = {'workload': workload, 'precision': precision, 'timestamp': timestamp, 'call': call, 'duration_ns': duration_ns, 'transa': None, 'transb': None, 'm': None, 'n': None, 'k': None, 'alpha': None, 'a': None, 'lda': None, 'ldb': None, 'beta': None, 'c': None, 'ldc': None, 'x': None, 'incx': None}
        row = {'workload': workload, 'seq_num': line_num, 'precision': precision, 'call': call, 'duration_ms': duration_ms, 'nthr': nthr, 'transa': None, 'transb': None, 'm': None, 'n': None, 'k': None, 'alpha': None, 'a': None, 'lda': None, 'ldb': None, 'beta': None, 'c': None, 'ldc': None, 'x': None, 'incx': None}
        if 'gemm_batch' in call.lower():
            row['transa'],row['transb'] = details.split(',')[:2]  #ignoring rest of line for now; don't know what it is
        elif 'gemm' in call.lower():
          if 'gemm_s8u8s32' in call.lower():
            #verify that precision is int8
            if (row['precision'] != 'int8'):
              print("NOTE: mkl gemm call; changing fp32 precision to int8")
              isMixedPrecision = True
              row['precision'] = 'int8'
            row['transa'],row['transb'],row['offsetc'],row['m'],row['n'],row['k'],row['alpha'],row['a'],row['lda'],row['oa'],row['b'],row['ldb'],row['ob'],row['beta'],row['c'],row['ldc'],row['oc'] = details.split(',')
          else:
            #verify that precision is fp32
            if (row['precision'] != 'fp32'):
              print("NOTE: mkl gemm call; changing int8 precision to fp32")
              isMixedPrecision = True
              row['precision'] = 'fp32'
            row['transa'],row['transb'],row['m'],row['n'],row['k'],row['alpha'],row['a'],row['lda'],row['b'],row['ldb'],row['beta'],row['c'],row['ldc'] = details.split(',')
          row['m'] = int(row['m'])
          row['n'] = int(row['n'])
          row['k'] = int(row['k'])
          row['FLOPS'] = 2 * row['m'] * row['n'] * row['k']
          bytes_per_element = 1 if row['precision'] == 'int8' else 4
          row['bytes'] = (row['m'] * row['k'] + row['n'] * row['k'] + row['m'] * row['n']) * bytes_per_element
          row['intensity'] = row['FLOPS'] / row['bytes']
          row['GFLOPS/s'] = row['FLOPS'] / ( row['duration_ms'] * 1e6 )
        elif 'asum' in call.lower():
          row['n'],row['x'],row['incx'] = details.split(',')
        elif 'scal' in call.lower():
          row['n'],row['a'],row['x'],row['incx'] = details.split(',')
        #elif 'sgemm_batch' in call.lower():
        #  row['m'] = 0 
        else:
          print("ERROR, unexpected MKL call %s for %s"%(call, workload, precision, log))
          return False
  
        row['seq_num'] = line_num
        total_mkl_time_ms += duration_ms
        mkl.append(row)

      elif 'mkldnn_verbose,' in line and 'Intel' not in line:
        MKLDNN_LINE = True
        details = re.split(',', re.split('\[|\]', line)[-1].strip().replace('\n','').replace(' ', '_'))
        row = {'workload': workload, 'precision': precision}
        row['seq_num'] = line_num
        #row['timestamp'] = timestamp
        row['call'] = call = details[1]
        row['primitive'] = primitive = details[2]
        row['implementation'] = implementation = details[3]
        row['propagation'] = details[4]
        row['input_output'] = details[5]
        row['auxiliary'] = details[6]
        row['post_ops'] = ''
        row['description'] = description = details[7]
        if 'eltwise' in primitive:
            row['primitive'] = primitive = details[6].split(':')[1]
        row['duration_ms'] = duration_ms = float(details[-1])
        total_mkldnn_time_ms += duration_ms

        if duration_ms <= 0:
          #print("WARNING, found zero duration", line, workload, precision, log)
          continue

        if 'convolution' in primitive and 'exec' in call:
          if 'g' in description:
            row.update(regex_g.match(description).groupdict())
          else:
            row.update(regex.match(description).groupdict())
            row['g'] = 1

          if (not isRome) and ('avx512' not in implementation):
            #verify that this is avx512
            print("ERROR: convolution vector width is not avx512; avx512 expected for CLX")
            sys.exit(2)

          if isRome and ('avx2' not in implementation):
            #verify that this is avx2
            print("ERROR: convolution vector width is not avx2; avx2 expected for Rome")
            sys.exit(2)

          #check precision
          if ('int8' in implementation):
            #int8 implementation
            if (row['precision'] != 'int8'):
                print("NOTE: convolution; fp32 precision changed to int8")
                isMixedPrecision = True
                row['precision'] = 'int8'
          else:
            #precision is fp32
            if (row['precision'] != 'fp32'):
                print("NOTE: convolution; int8 precision changed to fp32")
                isMixedPrecision = True
                row['precision'] = 'fp32'

          #print(row)

          #type
          if int(row['kh']) == 1 and int(row['kw']) == 1 and int(row['sh']) == 1 and int(row['sw']) == 1:
            row['type'] = '1x1'
          elif int(row['kh']) == 1 and int(row['kw']) == 1 and (int(row['sh']) > 1 or int(row['sw']) > 1):
            row['type'] = '1x1 strided'
          elif (int(row['kh']) > 1 or int(row['kw']) > 1) and int(row['sh']) == 1 or int(row['sw']) == 1:
            row['type'] = 'non-1x1'
          elif (int(row['kh']) > 1 or int(row['kw']) > 1) and (int(row['sh']) > 1 or int(row['sw']) > 1):
            row['type'] = 'non-1x1 strided'

          row['macs'] = (int(row['mb']) * int(row['ic']) * int(row['oc']) * int(row['oh']) * int(row['ow']) * int(row['kh']) * int(row['kw'])) / int(row['g'])
          row['macs/sec'] = row['macs'] / (row['duration_ms'] / 1e3)
          ideal_macspersec = ideal_macspersec_int8 if row['precision'] == 'int8' else ideal_macspersec_fp32
          try:
              row['ideal_time_ms'] = row['macs'] / ideal_macspersec * 1000
          except:
              row['ideal_time_ms'] = 0
          row['efficiency_%'] = (row['ideal_time_ms'] / row['duration_ms']) * 100

          # target efficiency
          if  precision == 'fp32':
            if row['type'] == '1x1':
              row['target_efficiency_%'] = 70
            elif row['type'] == '1x1 strided':
              row['target_efficiency_%'] = 70
            elif row['type'] == 'non-1x1':
              row['target_efficiency_%'] = 80
            elif row['type'] == 'non-1x1 strided':
              row['target_efficiency_%'] = 75
          elif  precision == 'int8':
            if row['type'] == '1x1':
              row['target_efficiency_%'] = 75
            elif row['type'] == '1x1 strided':
              row['target_efficiency_%'] = 75
            elif row['type'] == 'non-1x1':
              row['target_efficiency_%'] = 80
            elif row['type'] == 'non-1x1 strided':
              row['target_efficiency_%'] = 80

          #print("Target efficiency " + str(row['target_efficiency_%']))
          
          row['predicted_time_ms'] = row['ideal_time_ms'] / row['target_efficiency_%'] * 100
          row['input_ratio'] = int(row['ic']) / (int(row['ih']) * int(row['iw']))
          row['output_ratio'] = int(row['oc']) / (int(row['oh']) * int(row['ow']))
          row['weight_ratio'] = int(row['oc']) / int(row['ic'])
          row['input_ratio_bin'] = row['output_ratio_bin'] = row['weight_ratio_bin'] = None
          # ratio bins
          for ratio_bin in ratio_bins:
            if row['input_ratio_bin'] is None and row['input_ratio'] < ratio_bin * 1.5:
              row['input_ratio_bin'] = ratio_bin
            if row['output_ratio_bin'] is None and row['output_ratio'] < ratio_bin * 1.5:
              row['output_ratio_bin'] = ratio_bin
            if row['weight_ratio_bin'] is None and row['weight_ratio'] < ratio_bin * 1.5:
              row['weight_ratio_bin'] = ratio_bin
          if row['input_ratio_bin'] is None: row['input_ratio_bin'] = 'wider'
          if row['output_ratio_bin'] is None: row['output_ratio_bin'] = 'wider'
          if row['weight_ratio_bin'] is None: row['weight_ratio_bin'] = 'wider'
          # parameter size
          row['parameter_size'] = (int(row['kh']) * int(row['kw']) * int(row['ic']) * int(row['oc'])) / int(row['g']) + int(row['oc'])
          row['parameter_size_bin'] = 10 ** round(math.log10(row['parameter_size']))
          row['parameter_size_bin'] = (
            'huge' if row['parameter_size_bin'] >= 1e12 else
            str(int(row['parameter_size_bin'] / 1e9)) + 'G' if row['parameter_size_bin'] >= 1e9 else
            str(int(row['parameter_size_bin'] / 1e6)) + 'M' if row['parameter_size_bin'] >= 1e6 else
            str(int(row['parameter_size_bin'] / 1e3)) + 'K' if row['parameter_size_bin'] >= 1e3 else
            str(row['parameter_size_bin'])
          )
          row['input_weight_size_bins'] = str(row['input_ratio_bin']) + '_' + str(row['weight_ratio_bin']) + '_' + row['parameter_size_bin']
          mkldnn_convolution.append(row)
  
          kernel_name = description + '-' + row['precision']
          if kernel_name not in kernels:
            kernels[kernel_name] = {}
            kernels[kernel_name]['time_ms'] = 0
            kernels[kernel_name]['count'] = 0
            kernels[kernel_name]['efficiency_%'] = 0
            kernels[kernel_name]['target_efficiency_%'] = 0
            #kernels[description]['aspect_ratio'] = str(int((int(row['ih']) / int(row['iw'])) * int(row['ic']))) + 'x' + str(int((int(row['oh']) / int(row['ow'])) * int(row['oc'])))
            kernels[kernel_name]['input_weight_size_bins'] = row['input_weight_size_bins']
            kernels[kernel_name]['ideal_time_ms'] = 0
            kernels[kernel_name]['kernel_size'] = 0
          kernels[kernel_name]['time_ms'] += duration_ns
          kernels[kernel_name]['count'] += 1
          kernels[kernel_name]['efficiency_%'] = kernels[kernel_name]['efficiency_%'] + ((row['efficiency_%'] - kernels[kernel_name]['efficiency_%']) / kernels[kernel_name]['count'])
          kernels[kernel_name]['target_efficiency_%'] = row['target_efficiency_%']
          kernels[kernel_name]['ideal_time_ms'] += row['ideal_time_ms']
          kernels[kernel_name]['kernel_size'] = '[' + str(row['kh']) + 'x' + str(row['kw']) + ']'

        elif ('gemm:jit' in implementation or 'igemm_s8s8s32:jit' in implementation) and 'exec' in call:
          
          #print(row['description'])
          
          if 'gemm:jit' in implementation:
              #fp32 implementation
              if (row['precision'] != 'fp32'):
                row['precision'] = 'fp32'
                isMixedPrecision = True
                print("NOTE: gemm int8 precision changed to fp32")
          if 'igemm_s8s8s32:jit' in implementation:
              #int8 implementation
              if (row['precision'] != 'int8'):
                row['precision'] = 'int8'
                isMixedPrecision = True
                print("NOTE: igemm_s8s8s32 fp32 precision changed to int8")

          row.update(regex_gemm.match(description).groupdict())
          row['g'] = 1
          
          #print(row)

          row['kh'] = 0
          row['dh'] = 0
          row['ph'] = 0
          row['sw'] = 0
          row['pw'] = 0
          row['dw'] = 0
          row['ih'] = 0
          row['iw'] = 0
          row['oh'] = 0
          row['ow'] = 0
          row['kw'] = 0
          row['sh'] = 0

          row['macs'] = (int(row['mb']) * int(row['ic']) * int(row['oc']))
          row['macs/sec'] = row['macs'] / (row['duration_ms'] /1e3)
          ideal_macspersec = ideal_macspersec_int8 if row['precision'] == 'int8' else ideal_macspersec_fp32
          try:
              row['ideal_time_ms'] = (row['macs'] / ideal_macspersec) * 1000
          except:
              row['ideal_time_ms'] = 0
          row['efficiency_%'] = (row['ideal_time_ms'] / row['duration_ms']) * 100
          row['target_efficiency_%'] = 100
          
          row['predicted_time_ms'] = row['ideal_time_ms'] / row['target_efficiency_%'] * 100
          row['input_ratio'] = int(row['ic']) / int(row['mb'])  ## k/m
          row['output_ratio'] = int(row['oc']) / int(row['mb'])   ## n/m
          row['weight_ratio'] = int(row['oc']) / int(row['ic'])
          row['input_ratio_bin'] = row['output_ratio_bin'] = row['weight_ratio_bin'] = None
          # ratio bins
          for ratio_bin in ratio_bins:
            if row['input_ratio_bin'] is None and row['input_ratio'] < ratio_bin * 1.5:
              row['input_ratio_bin'] = ratio_bin
            if row['output_ratio_bin'] is None and row['output_ratio'] < ratio_bin * 1.5:
              row['output_ratio_bin'] = ratio_bin
            if row['weight_ratio_bin'] is None and row['weight_ratio'] < ratio_bin * 1.5:
              row['weight_ratio_bin'] = ratio_bin
          if row['input_ratio_bin'] is None: row['input_ratio_bin'] = 'wider'
          if row['output_ratio_bin'] is None: row['output_ratio_bin'] = 'wider'
          if row['weight_ratio_bin'] is None: row['weight_ratio_bin'] = 'wider'
          # parameter size
          row['parameter_size'] = int(row['ic']) * int(row['oc'])
          row['parameter_size_bin'] = 10 ** round(math.log10(row['parameter_size']))
          row['parameter_size_bin'] = (
            'huge' if row['parameter_size_bin'] >= 1e12 else
            str(int(row['parameter_size_bin'] / 1e9)) + 'G' if row['parameter_size_bin'] >= 1e9 else
            str(int(row['parameter_size_bin'] / 1e6)) + 'M' if row['parameter_size_bin'] >= 1e6 else
            str(int(row['parameter_size_bin'] / 1e3)) + 'K' if row['parameter_size_bin'] >= 1e3 else
            str(row['parameter_size_bin'])
          )
          row['input_weight_size_bins'] = str(row['input_ratio_bin']) + '_' + str(row['weight_ratio_bin']) + '_' + row['parameter_size_bin']
          #print(row)
          
          mkldnn_convolution.append(row)
  
          kernel_name = description + '-' + row['precision']
          if kernel_name not in kernels:
            kernels[kernel_name] = {}
            kernels[kernel_name]['time_ms'] = 0
            kernels[kernel_name]['count'] = 0
            kernels[kernel_name]['efficiency_%'] = 0
            kernels[kernel_name]['target_efficiency_%'] = 0 
            #kernels[description]['aspect_ratio'] = str(int((int(row['ih']) / int(row['iw'])) * int(row['ic']))) + 'x' + str(int((int(row['oh']) / int(row['ow'])) * int(row['oc'])))
            kernels[kernel_name]['input_weight_size_bins'] = row['input_weight_size_bins']
            kernels[kernel_name]['ideal_time_ms'] = 0
            kernels[kernel_name]['kernel_size'] = 0 
          kernels[kernel_name]['time_ms'] += duration_ms
          kernels[kernel_name]['count'] += 1
          kernels[kernel_name]['efficiency_%'] = kernels[kernel_name]['efficiency_%'] + ((row['efficiency_%'] - kernels[kernel_name]['efficiency_%']) / kernels[kernel_name]['count'])
          kernels[kernel_name]['target_efficiency_%'] = row['target_efficiency_%']
          kernels[kernel_name]['ideal_time_ms'] += row['ideal_time_ms']
          kernels[kernel_name]['kernel_size'] = ''
          #df.apply(lambda x: '[' + str(x['ic']) + ',' + str(x['oc']) + ',' + str(x['kh'] * x['kw']) + ']', axis=1)

        else: # non-convolution
          if 'src_f32' in row['input_output'] or 'data_f32' in row['input_output']:
            row['precision'] = 'fp32'
          elif 'src_s8' in row['input_output'] or 'src_u8' in row['input_output'] or 'data_s8' in row['input_output'] or 'data_u8' in row['input_output']:
            row['precision'] = 'int8'
          else:
            row['precision'] = 'NA'
          mkldnn_non_convolution.append(row)

      ### MKLDNN VERBOSE ###
      elif 'dnnl_verbose,' in line and 'info' not in line:
        MKLDNN_LINE = True
        details = re.split(',', re.split('\[|\]', line)[-1].strip().replace('\n','').replace(' ', '_'))
        #print("details")
        #print(details)
        #print("row" + str(row))
        row = {'workload': workload, 'precision': precision}
        row['seq_num'] = line_num
        #row['timestamp'] = timestamp
        row['call'] = call = details[1]
        row['primitive'] = primitive = details[3]
        row['implementation'] = implementation = details[4]
        row['propagation'] = details[5]
        row['input_output'] = details[6]
        row['post_ops'] = details[7]
        row['auxiliary'] = details[8]
        row['description'] = description = details[9]
        row['duration_ms'] = duration_ms = float(details[-1])
        if 'eltwise' in primitive:
            row['primitive'] = primitive = details[8].split(' ')[0].split(':')[1]
        total_mkldnn_time_ms += duration_ms

        if duration_ms <= 0:
          #print("WARNING, found zero duration", line, workload, precision, log)
          continue

        if 'convolution' in primitive and 'exec' in call:
          if 'g' in description:
            row.update(regex_g.match(description).groupdict())
          else:
            row.update(regex.match(description).groupdict())
            row['g'] = 1
          
          if (not isRome) and ('avx512' not in implementation):
            #verify that this is avx512
            print("ERROR: convolution vector width is not avx512; avx512 expected for CLX")
            sys.exit(2)

          if isRome and ('avx2' not in implementation):
            #verify that this is avx2
            print("ERROR: convolution vector width is not avx2; avx2 expected for Rome")
            sys.exit(2)

          #check precision
          if ('int8' in implementation):
            #int8 implementation
            if (row['precision'] != 'int8'):
                print("NOTE: convolution fp32 precision changed to in8")
                isMixedPrecision = True
                row['precision'] = 'int8'
          else:
            #precision is fp32
            if (row['precision'] != 'fp32'):
                print("NOTE: convolution int8 precision changed to fp32")
                isMixedPrecision = True
                row['precision'] = 'fp32'

          #print(row)

          #type
          if int(row['kh']) == 1 and int(row['kw']) == 1 and int(row['sh']) == 1 and int(row['sw']) == 1:
            row['type'] = '1x1'
          elif int(row['kh']) == 1 and int(row['kw']) == 1 and (int(row['sh']) > 1 or int(row['sw']) > 1):
            row['type'] = '1x1 strided'
          elif (int(row['kh']) > 1 or int(row['kw']) > 1) and int(row['sh']) == 1 or int(row['sw']) == 1:
            row['type'] = 'non-1x1'
          elif (int(row['kh']) > 1 or int(row['kw']) > 1) and (int(row['sh']) > 1 or int(row['sw']) > 1):
            row['type'] = 'non-1x1 strided'

          row['macs'] = (int(row['mb']) * int(row['ic']) * int(row['oc']) * int(row['oh']) * int(row['ow']) * int(row['kh']) * int(row['kw'])) / int(row['g'])
          row['macs/sec'] = row['macs'] / (row['duration_ms'] / 1e3)
          ideal_macspersec = ideal_macspersec_int8 if row['precision'] == 'int8' else ideal_macspersec_fp32
          try:
              row['ideal_time_ms'] = (row['macs'] / ideal_macspersec) * 1000
          except:
              row['ideal_time_ms'] = 0
          row['efficiency_%'] = (row['ideal_time_ms'] / row['duration_ms']) * 100
          
          # target efficiency
          if  precision == 'fp32':
            if row['type'] == '1x1':
              row['target_efficiency_%'] = 70
            elif row['type'] == '1x1 strided':
              row['target_efficiency_%'] = 70
            elif row['type'] == 'non-1x1':
              row['target_efficiency_%'] = 80
            elif row['type'] == 'non-1x1 strided':
              row['target_efficiency_%'] = 75
          elif  precision == 'int8':
            if row['type'] == '1x1':
              row['target_efficiency_%'] = 75
            elif row['type'] == '1x1 strided':
              row['target_efficiency_%'] = 75
            elif row['type'] == 'non-1x1':
              row['target_efficiency_%'] = 80
            elif row['type'] == 'non-1x1 strided':
              row['target_efficiency_%'] = 80

          #print("Target efficiency " + str(row['target_efficiency_%']))
          
          row['predicted_time_ms'] = row['ideal_time_ms'] / row['target_efficiency_%'] * 100
          row['input_ratio'] = int(row['ic']) / (int(row['ih']) * int(row['iw']))
          row['output_ratio'] = int(row['oc']) / (int(row['oh']) * int(row['ow']))
          row['weight_ratio'] = int(row['oc']) / int(row['ic'])
          row['input_ratio_bin'] = row['output_ratio_bin'] = row['weight_ratio_bin'] = None
          # ratio bins
          for ratio_bin in ratio_bins:
            if row['input_ratio_bin'] is None and row['input_ratio'] < ratio_bin * 1.5:
              row['input_ratio_bin'] = ratio_bin
            if row['output_ratio_bin'] is None and row['output_ratio'] < ratio_bin * 1.5:
              row['output_ratio_bin'] = ratio_bin
            if row['weight_ratio_bin'] is None and row['weight_ratio'] < ratio_bin * 1.5:
              row['weight_ratio_bin'] = ratio_bin
          if row['input_ratio_bin'] is None: row['input_ratio_bin'] = 'wider'
          if row['output_ratio_bin'] is None: row['output_ratio_bin'] = 'wider'
          if row['weight_ratio_bin'] is None: row['weight_ratio_bin'] = 'wider'
          # parameter size
          row['parameter_size'] = (int(row['kh']) * int(row['kw']) * int(row['ic']) * int(row['oc'])) / int(row['g']) + int(row['oc'])
          #print(row['parameter_size'])
          row['parameter_size_bin'] = 10 ** round(math.log10(row['parameter_size']))
          row['parameter_size_bin'] = (
            'huge' if row['parameter_size_bin'] >= 1e12 else
            str(int(row['parameter_size_bin'] / 1e9)) + 'G' if row['parameter_size_bin'] >= 1e9 else
            str(int(row['parameter_size_bin'] / 1e6)) + 'M' if row['parameter_size_bin'] >= 1e6 else
            str(int(row['parameter_size_bin'] / 1e3)) + 'K' if row['parameter_size_bin'] >= 1e3 else
            str(row['parameter_size_bin'])
          )
          row['input_weight_size_bins'] = str(row['input_ratio_bin']) + '_' + str(row['weight_ratio_bin']) + '_' + row['parameter_size_bin']
          #print(row)
          mkldnn_convolution.append(row)
  
          if description not in kernels:
            kernels[description] = {}
            kernels[description]['time_ms'] = 0
            kernels[description]['count'] = 0
            kernels[description]['efficiency_%'] = 0
            kernels[description]['target_efficiency_%'] = 0
            #kernels[description]['aspect_ratio'] = str(int((int(row['ih']) / int(row['iw'])) * int(row['ic']))) + 'x' + str(int((int(row['oh']) / int(row['ow'])) * int(row['oc'])))
            kernels[description]['input_weight_size_bins'] = row['input_weight_size_bins']
            kernels[description]['ideal_time_ms'] = 0
            kernels[description]['kernel_size'] = 0
          kernels[description]['time_ms'] += duration_ms
          kernels[description]['count'] += 1
          kernels[description]['efficiency_%'] = kernels[description]['efficiency_%'] + ((row['efficiency_%'] - kernels[description]['efficiency_%']) / kernels[description]['count'])
          kernels[description]['target_efficiency_%'] = row['target_efficiency_%']
          kernels[description]['ideal_time_ms'] += row['ideal_time_ms']
          kernels[description]['kernel_size'] = '[' + str(row['kh']) + 'x' + str(row['kw']) + ']'

        elif ('gemm:jit' in implementation or 'igemm_s8s8s32:jit' in implementation) and 'exec' in call:
          
          #print(row['description'])
          
          if 'gemm:jit' in implementation:
              if (row['precision'] != 'fp32'):
                row['precision'] = 'fp32'
                isMixedPrecision = True
                print("NOTE: gemm int8 precision changed to fp32")
          if 'igemm_s8s8s32:jit' in implementation:
              if (row['precision'] != 'int8'):
                row['precision'] = 'int8'
                isMixedPrecision = True
                print("NOTE: igemm_s8s8s32 fp32 precision changed to int8")
          
          
          row.update(regex_gemm.match(description).groupdict())
          row['g'] = 1
          
          #print(row)

          row['kh'] = 0
          row['dh'] = 0
          row['ph'] = 0
          row['sw'] = 0
          row['pw'] = 0
          row['dw'] = 0
          row['ih'] = 0
          row['iw'] = 0
          row['oh'] = 0
          row['ow'] = 0
          row['kw'] = 0
          row['sh'] = 0

          row['macs'] = (int(row['mb']) * int(row['ic']) * int(row['oc']))
          row['macs/sec'] = row['macs'] / (row['duration_ms'] /1e3)
          ideal_macspersec = ideal_macspersec_int8 if row['precision'] == 'int8' else ideal_macspersec_fp32
          try:
              row['ideal_time_ms'] = (row['macs'] / ideal_macspersec) * 1000
          except:
              row['ideal_time_ms'] = 0
          row['efficiency_%'] = (row['ideal_time_ms'] / row['duration_ms']) * 100
          row['target_efficiency_%'] = 100
          
          row['predicted_time_ms'] = row['ideal_time_ms'] / row['target_efficiency_%'] * 100
          row['input_ratio'] = int(row['ic']) / int(row['mb'])  ## k/m
          row['output_ratio'] = int(row['oc']) / int(row['mb'])   ## n/m
          row['weight_ratio'] = int(row['oc']) / int(row['ic'])
          row['input_ratio_bin'] = row['output_ratio_bin'] = row['weight_ratio_bin'] = None
          # ratio bins
          for ratio_bin in ratio_bins:
            if row['input_ratio_bin'] is None and row['input_ratio'] < ratio_bin * 1.5:
              row['input_ratio_bin'] = ratio_bin
            if row['output_ratio_bin'] is None and row['output_ratio'] < ratio_bin * 1.5:
              row['output_ratio_bin'] = ratio_bin
            if row['weight_ratio_bin'] is None and row['weight_ratio'] < ratio_bin * 1.5:
              row['weight_ratio_bin'] = ratio_bin
          if row['input_ratio_bin'] is None: row['input_ratio_bin'] = 'wider'
          if row['output_ratio_bin'] is None: row['output_ratio_bin'] = 'wider'
          if row['weight_ratio_bin'] is None: row['weight_ratio_bin'] = 'wider'
          # parameter size
          row['parameter_size'] = int(row['ic']) * int(row['oc'])
          row['parameter_size_bin'] = 10 ** round(math.log10(row['parameter_size']))
          row['parameter_size_bin'] = (
            'huge' if row['parameter_size_bin'] >= 1e12 else
            str(int(row['parameter_size_bin'] / 1e9)) + 'G' if row['parameter_size_bin'] >= 1e9 else
            str(int(row['parameter_size_bin'] / 1e6)) + 'M' if row['parameter_size_bin'] >= 1e6 else
            str(int(row['parameter_size_bin'] / 1e3)) + 'K' if row['parameter_size_bin'] >= 1e3 else
            str(row['parameter_size_bin'])
          )
          row['input_weight_size_bins'] = str(row['input_ratio_bin']) + '_' + str(row['weight_ratio_bin']) + '_' + row['parameter_size_bin']
          #print(row)
          
          mkldnn_convolution.append(row)
  
          if description not in kernels:
            kernels[description] = {}
            kernels[description]['time_ms'] = 0
            kernels[description]['count'] = 0
            kernels[description]['efficiency_%'] = 0
            kernels[description]['target_efficiency_%'] = 0 
            #kernels[description]['aspect_ratio'] = str(int((int(row['ih']) / int(row['iw'])) * int(row['ic']))) + 'x' + str(int((int(row['oh']) / int(row['ow'])) * int(row['oc'])))
            kernels[description]['input_weight_size_bins'] = row['input_weight_size_bins']
            kernels[description]['ideal_time_ms'] = 0
            kernels[description]['kernel_size'] = 0 
          kernels[description]['time_ms'] += duration_ms
          kernels[description]['count'] += 1
          kernels[description]['efficiency_%'] = kernels[description]['efficiency_%'] + ((row['efficiency_%'] - kernels[description]['efficiency_%']) / kernels[description]['count'])
          kernels[description]['target_efficiency_%'] = row['target_efficiency_%']
          kernels[description]['ideal_time_ms'] += row['ideal_time_ms']
          kernels[description]['kernel_size'] = ''
          #df.apply(lambda x: '[' + str(x['ic']) + ',' + str(x['oc']) + ',' + str(x['kh'] * x['kw']) + ']', axis=1)
          
        else: # non-convolution
          if 'src_f32' in row['input_output'] or 'data_f32' in row['input_output']:
            row['precision'] = 'fp32'
          elif 'src_s8' in row['input_output'] or 'src_u8' in row['input_output'] or 'data_s8' in row['input_output'] or 'data_u8' in row['input_output']:
            row['precision'] = 'int8'
          else:
            row['precision'] = 'NA'
          mkldnn_non_convolution.append(row)

        #print(row)

      if MKL_LINE or MKLDNN_LINE:
        if primitive not in primitives:
          primitives[primitive] = {}
          primitives[primitive]['time_ms'] = 0
          primitives[primitive]['count'] = 0
        primitives[primitive]['time_ms'] += duration_ms
        primitives[primitive]['count'] += 1

      if line_num % 1e6 == 0:
        print("\tprocessed", line_num, workload, precision)
    except:
      print("ERROR", workload, precision, line_num, line, str(traceback.format_exc()))
      return False

  #print(mkldnn_convolution)
  # add some more metrics to main dataffame
  desiredOrder_nonConvolution = ['workload','seq_num','precision','call','primitive','implementation','propagation','input_output','auxiliary','description','duration_ms']
  desiredOrder_convolution = ['workload','seq_num','precision','call','primitive','implementation','propagation','input_output','auxiliary','description','post_ops','duration_ms','mb','ic','oc','ih','oh','kh','sh','dh','ph','iw','ow','kw','sw','dw','pw','g','macs','macs/sec','ideal_time_ms','efficiency_%', 'target_efficiency_%', 'predicted_time_ms', 'input_ratio','output_ratio','weight_ratio','input_ratio_bin','output_ratio_bin','weight_ratio_bin','parameter_size','parameter_size_bin','input_weight_size_bins']
  desiredOrder_mkl = ['workload', 'seq_num', 'precision', 'call', 'duration_ms', 'nthr', 'transa', 'transb', 'm', 'n', 'k', 'alpha', 'a', 'lda', 'ldb', 'beta', 'c', 'ldc', 'x', 'incx']
  total_mkl_mkldnn_time_ms = total_mkldnn_time_ms + total_mkl_time_ms
  mkl_df = pd.DataFrame.from_dict(mkl)
  if len(mkl_df) > 0:
     mkl_df = mkl_df[desiredOrder_mkl]
  #print("mkl_df")
  #print(mkl_df.columns)
  non_convolution_df = pd.DataFrame.from_dict(mkldnn_non_convolution)
  if len(non_convolution_df) > 0:
     non_convolution_df = non_convolution_df[desiredOrder_nonConvolution]
  #print("non_convolution_df")
  #print(non_convolution_df.columns)
  df = pd.DataFrame.from_dict(mkldnn_convolution)
  if len(df) > 0:
     df = df[desiredOrder_convolution]
  #print("mkl_convolution_df")
  #print(df.columns)

  if len(df) > 0:
    total_convolution_time_ms = df['duration_ms'].sum()
    df['duration_%_convolutions'] = (df['duration_ms'] / total_convolution_time_ms) * 100 # percent of only time spent in convolutions
    df['weighted_efficiency_%'] = df.apply(lambda x: x['efficiency_%'] * (x['duration_%_convolutions'] / 100), axis=1)
    df[['mb', 'ic', 'oc', 'ih', 'oh', 'kh', 'sh', 'dh', 'ph', 'iw', 'ow', 'kw', 'sw', 'dw', 'pw', 'g']] = df[['mb', 'ic', 'oc', 'ih', 'oh', 'kh', 'sh', 'dh', 'ph', 'iw', 'ow', 'kw', 'sw', 'dw', 'pw', 'g']].astype(float)
    #df[['mb', 'ic', 'oc', 'g']] = df[['mb', 'ic', 'oc', 'g']].astype(int)
    df['FLOPS'] = df['macs'] * 2
    df['GFLOPS/s'] = df['FLOPS'] / (df['duration_ms'] * 1e6)

    # if convolution
    df.loc[df['primitive'] == "convolution",'input_size'] = df['ih'] * df['iw'] * df['ic']
    df.loc[df['primitive'] == "convolution",'input_shape'] = df.apply(lambda x: '[' + str(x['mb']) + ',' + str(x['ih']) + ',' + str(x['iw']) + ',' + str(x['ic']) + ']', axis=1)
    df.loc[df['primitive'] == "convolution",'output_size'] = df['oh'] * df['ow'] * df['oc']
    df.loc[df['primitive'] == "convolution",'output_shape'] = df.apply(lambda x: '[' + str(x['mb']) + ',' + str(x['oh']) + ',' + str(x['ow']) + ',' + str(x['oc']) + ']', axis=1)
    df.loc[df['primitive'] == "convolution",'weight_size'] = (df['kh'] * df['kw'] * df['ic'] * df['oc']) / df['g']
    df.loc[df['primitive'] == "convolution",'weight_shape'] = df.apply(lambda x: '[' + str(x['ic']) + ',' + str(x['oc']) + ',' + str(x['kh'] * x['kw']) + ']', axis=1)
    df.loc[df['primitive'] == "convolution",'parameter_size'] = (df['kh'] * df['kw'] * df['ic'] * df['oc']) / df['g'] + df['oc']

    # if gemm 
    df.loc[df['primitive'] != "convolution",'input_size'] = df['mb'] * df['ic']
    df.loc[df['primitive'] != "convolution",'input_shape'] = df.apply(lambda x: '[' + str(x['mb']) + ',' + str(x['ic']) + ']', axis=1)
    df.loc[df['primitive'] != "convolution",'output_size'] = df['mb'] * df['oc']
    df.loc[df['primitive'] != "convolution",'output_shape'] = df.apply(lambda x: '[' + str(x['mb']) + ',' + str(x['oc']) + ']', axis=1)
    df.loc[df['primitive'] != "convolution",'weight_size'] = df['ic'] * df['oc']
    df.loc[df['primitive'] != "convolution",'weight_shape'] = df.apply(lambda x: '[' + str(x['ic']) + ',' + str(x['oc']) + ']', axis=1)
    df.loc[df['primitive'] != "convolution", 'parameter_size'] = (df['ic'] * df['oc']) + df['oc']

    #bytes_per_element = 1 if df['precision'] == 'int8' else 4
    df['input_bytes'] = df.apply(lambda x: (x['input_size'] if x['precision'] == 'int8' else x['input_size']*4), axis=1)
    df['output_bytes'] = df.apply(lambda x: (x['output_size'] if x['precision'] == 'int8' else x['output_size']*4), axis=1)
    df['weight_bytes'] = df.apply(lambda x: (x['weight_size'] if x['precision'] == 'int8' else x['weight_size']*4), axis=1)
    df['parameter_size_bin'] = df.apply(lambda x: 10 ** round(math.log10(x['parameter_size'])), axis=1)
    df['parameter_size_bin'] = df.apply(lambda x: (
      str(int(x['parameter_size_bin'] / 1e9)) + 'G' if x['parameter_size_bin'] >= 1e9 else
      str(int(x['parameter_size_bin'] / 1e6)) + 'M' if x['parameter_size_bin'] >= 1e6 else
      str(int(x['parameter_size_bin'] / 1e3)) + 'K' if x['parameter_size_bin'] >= 1e3 else
      str(x['parameter_size_bin'])
    ), axis=1)
    df['total_bytes'] = df['input_bytes'] + df['output_bytes'] + df['weight_bytes']
    df['bandwidth_GB/s'] = df['total_bytes'] / (df['duration_ms'] * 1e6)
    df['bandwidth_util_%'] = (df['bandwidth_GB/s'] / peak_gbps) * 100
    df['intensity'] = df['FLOPS'] / df['total_bytes']
    df['intensity_weight'] = df['FLOPS'] / df['weight_bytes']
    df['possible_GFLOPS/s'] = df.apply(lambda x: min(peak_gops, x['intensity'] * peak_gbps), axis=1)
    df['fp_efficiency_%'] = df['GFLOPS/s'] / df['possible_GFLOPS/s'] * 100
    df['fp_util_%'] = df['GFLOPS/s'] / peak_gops * 100
    #df['tmul_efficiency_%'] = df.apply(lambda x: ((x['ic'] % 64) + (math.floor(x['ic']/64) * 64)) / (math.ceil(x['ic'] / 64) * 64) * 0.5 *  (x['efficiency_%'] / 100) * 100 if precision == 'int8' else x['efficiency_%'], axis=1)
    #df['tmul_time_ms'] = df['macs'] / (tmul_ideal_macspersec_percore * num_cores * freq * 1e9 * (df['tmul_efficiency_%'] / 100)) * 1e3
    #df['tmul_speedup'] = df['duration_ms'] / df['tmul_time_ms']


  # create stats df
  stats = {
    'workload': workload_config,
    #'verbose_workload_wallclock_sec': (workload_end - workload_start).total_seconds() if workload_end is not None and workload_start is not None else None,
    'verbose_workload_wallclock_sec': verbose_times[workload_config] if workload_config in verbose_times else 0,
    'non_verbose_workload_wallclock_sec': non_verbose_times[workload_config] if workload_config in non_verbose_times else 0,
    'MKLDNN_execution_sec': total_mkldnn_time_ms / 1e3,
    'MKL_execution_sec': total_mkl_time_ms / 1e3,
    'MKL_MKLDNN_execution_sec': total_mkl_mkldnn_time_ms / 1e3,
    'num_cores': num_cores,
    'freq': freq,
    'vector_units_per_core': vector_units_per_core,
    'ideal_macspersec_fp32': ideal_macspersec_fp32,
    'ideal_macspersec_int8': ideal_macspersec_int8,
    'dram_channels': dram_channels,
    'peak_gbps': peak_gbps,
    'peak_gops': peak_gops,
    'roofline_intensity': peak_gops / peak_gbps,
    'avg_weighted_efficiency_%': df['weighted_efficiency_%'].sum() if 'weighted_efficiency_%' in df else None,
    'model_size': df['parameter_size'].sum() if 'parameter_size' in df and isSingleIter else None,
  }
  if len(df) > 0:
    #print("In stats len df")
    if df['predicted_time_ms'].sum() == 0:
        stats['avg_target_efficiency_%'] = 0
    else:
        stats['avg_target_efficiency_%'] = df['ideal_time_ms'].sum()*100/df['predicted_time_ms'].sum()
  if stats['non_verbose_workload_wallclock_sec'] > 0:
    total_runtime = stats['non_verbose_workload_wallclock_sec']
  else:
    total_runtime = stats['MKL_MKLDNN_execution_sec']
  stats['time_sec_outside_mkl_mkldnn'] = stats['non_verbose_workload_wallclock_sec'] - stats['MKL_MKLDNN_execution_sec']
  stats['time_%_outside_mkl_mkldnn'] = stats['time_sec_outside_mkl_mkldnn'] / total_runtime * 100
  # TODO currently only comprehends speedup of convolutions (duration_ns), need to add SGEMM speedup
  #stats['tmul_workload_speedup_%'] = ((df['duration_ms'].sum()) - df['tmul_time_ms'].sum()) / (non_verbose_times[workload_config] * 1000) * 100 if 'duration_ms' in df else None

  #if(stats['MKL_MKLDNN_execution_sec'] > stats['verbose_workload_wallclock_sec']):
    #print("\tWARNING", workload, precision, stats['MKL_MKLDNN_execution_sec'], stats['verbose_workload_wallclock_sec'])
  

  # create primitive df
  if workload_config in non_verbose_times and non_verbose_times[workload_config] > 0:
      total_runtime = non_verbose_times[workload_config]
  else:
      total_runtime = total_mkl_mkldnn_time_ms
  primitives['other'] = {'time_ms': (total_runtime * 1e3)  - total_mkl_mkldnn_time_ms, 'count': None}  
  p_row = {'workload': workload_config}
  #print(p_row)
  #print("primitives non verbose time " + str(non_verbose_times[workload_config]))
  for primitive,values in primitives.items():
    primitives[primitive]['time_%'] = values['time_ms'] / (total_runtime * 1e3) * 100
    p_row[primitive] = primitives[primitive]['time_%']
  #print("After for loop")
  #print(p_row)


  # create kernel df
  k_row_time = {'workload': workload_config}
  k_row_eff = {'workload': workload_config}
  total_kernel_time = 0 
  if 'convolution' in primitives:
      total_kernel_time += primitives['convolution']['time_ms']
  if 'inner_product' in primitives:
      total_kernel_time += primitives['inner_product']['time_ms']
  for kernel,values in kernels.items():
    #kernels[kernel]['time_%'] = (values['time_ms'] / (primitives['convolution']['time_ms']+primitives['inner_product']['time_ms'])) * 100
    kernels[kernel]['time_%'] = (values['time_ms'] / total_kernel_time) * 100
    #k_row_time[kernel] = kernels[kernel]['time_%']
    #k_row_eff[kernel] = kernels[kernel]['efficiency_%']
    if values['input_weight_size_bins'] not in k_row_time:
      k_row_time[values['input_weight_size_bins']] = 0
    k_row_time[values['input_weight_size_bins']] += kernels[kernel]['time_%']
    if values['input_weight_size_bins'] not in k_row_eff:
      k_row_eff[values['input_weight_size_bins']] = {}
      k_row_eff[values['input_weight_size_bins']]['value'] = 0
      k_row_eff[values['input_weight_size_bins']]['count'] = 0
    k_row_eff[values['input_weight_size_bins']]['count'] += 1
    k_row_eff[values['input_weight_size_bins']]['value'] = k_row_eff[values['input_weight_size_bins']]['value'] + ((kernels[kernel]['efficiency_%'] - k_row_eff[values['input_weight_size_bins']]['value']) / k_row_eff[values['input_weight_size_bins']]['count'])

  # drop the count
  for key,val in k_row_eff.items():
    if key != 'workload':
      k_row_eff[key] = val['value']


  # save stats to compare across workloads
  all_timings.append(stats)
  all_primitives.append(p_row)
  all_kernels_time.append(k_row_time)
  all_kernels_eff.append(k_row_eff)


  # create excel
  print("Results stored at " + resultdir)
  if not isSingleIter:
    output = resultdir + '/results/' + workload_config + '_mkldnn.xlsx'
  else:
    output = resultdir + '/results_singleIter/' + workload_config + '_mkldnn_singleIter.xlsx'
  print("\t", output)
  if not isSingleIter:
    os.system('mkdir -p ' + resultdir + '/results')
  else:
    os.system('mkdir -p ' + resultdir + '/results_singleIter')
  writer = pd.ExcelWriter(output, engine='xlsxwriter')
  workbook = writer.book

  primitives_df = pd.DataFrame.from_dict(primitives).transpose()
  if 'time_%' in primitives_df:
    primitives_df = primitives_df.sort_values(by=['time_%'], ascending=False)

  kernels_df = pd.DataFrame.from_dict(kernels).transpose()
  if 'time_%' in kernels_df:
    kernels_df = kernels_df.sort_values(by=['time_%'], ascending=False)

  stats_df = pd.DataFrame.from_dict([stats]).transpose()

  print("Writing to excel")
  if not isSingleIter:
    df.iloc[0:len(df)].to_excel(writer, sheet_name='MKLDNN GEMMs', index=False)
    non_convolution_df.iloc[0:len(non_convolution_df)].to_excel(writer, sheet_name='MKLDNN Non-GEMMs', index=False)
    mkl_sheet_created = True
    try:
      mkl_df.iloc[0:len(mkl_df)].to_excel(writer, sheet_name='MKL', index=False)
    except:
      mkl_sheet_created = False
      mkl_csv = mkl_df.iloc[0:len(mkl_df)].to_csv(resultdir + '/results/' + workload_config + '_mkl.csv', index=False)
      print("WARNING: Could not add MKL log to excel file; creating separate csv file instead")
  else:
    all_ops_df = pd.concat([df, non_convolution_df], axis=0, sort=False)
    all_ops_df = pd.concat([all_ops_df, mkl_df], axis=0, sort=False)
    all_ops_df = all_ops_df.sort_values(by=['seq_num'], ascending=True)
    if len(all_ops_df) > 0:
      all_ops_df.iloc[0:len(all_ops_df)].to_excel(writer, sheet_name='Operations', index=False)
  primitives_df.to_excel(writer, sheet_name='Primitives')
  kernels_df.to_excel(writer, sheet_name='Kernels')
  stats_df.to_excel(writer, sheet_name='Stats')
  
  
  # add chart(s)
  print("Adding charts")

  #print(df)
  #print(df["intensity"], df["GFLOPS/s"])
  if isSingleIter and len(all_ops_df) > 0:
    print("Creating chart\n")
    conv_worksheet = workbook.get_worksheet_by_name('Operations')
    chart = workbook.add_chart({'type': 'scatter', 'subtype': 'straight'})
    start = 1 # first row is header
    end = min(len(all_ops_df), 1e6) # excel can't show more than 1 million rows
    #print("DF start ",start," DF end ",end,"\n")
    chart.add_series({
      # sheet name, start row, start col, end row, end col
      'name': 'MKLDNN_' + workload + '_' + str(num_cores) + 'core_' + precision,
      'categories': ['Operations', start, all_ops_df.columns.get_loc("intensity"), end, all_ops_df.columns.get_loc("intensity")],
      'values': ['Operations', start, all_ops_df.columns.get_loc("GFLOPS/s"), end, all_ops_df.columns.get_loc("GFLOPS/s")],
      'line': {'none': True},
      'marker': {'type': 'automatic'},
    })
    '''
    if len(mkl_df) > 0 and 'intensity' in mkl_df:
        start = 1 # first row is header
        end = min(len(mkl_df), 1e6) # excel can't show more than 1 million rows
        #print("MKLDF start ",start," MKLDF end ",end,"\n")
        chart.add_series({
            # sheet name, start row, start col, end row, end col
            'name': 'MKL_' + workload + '_' + str(num_cores) + 'core_' + precision,
            'categories': ['Operations', start, mkl_df.columns.get_loc("intensity"), end, mkl_df.columns.get_loc("intensity")],
            'values': ['Operations', start, mkl_df.columns.get_loc("GFLOPS/s"), end, mkl_df.columns.get_loc("GFLOPS/s")],
            'line': {'none': True},
            'marker': {'type': 'automatic'},
        })
    '''
    if not isMixedPrecision:
        chart.add_series({
            'name': machine + '_' + str(num_cores) + 'core_' + precision,
            'categories': '={1e-100,' + str(inflection) + ',1e5}',
            'values': '={1e-100,' + str(peak_gops) + ',' + str(peak_gops) + '}',
        })
        chart.set_title({
            'name': workload + ' ' + precision + ' Roofline',
            'name_font': {'size': 18},
        })
    else:
        chart.add_series({
            'name': machine + '_' + str(num_cores) + 'core_' + 'fp32',
            'categories': '={1e-100,' + str(inflection_fp32) + ',1e5}',
            'values': '={1e-100,' + str(peak_gops_fp32) + ',' + str(peak_gops_fp32) + '}',
        })
        chart.add_series({
            'name': machine + '_' + str(num_cores) + 'core_' + 'int8',
            'categories': '={1e-100,' + str(inflection_int8) + ',1e5}',
            'values': '={1e-100,' + str(peak_gops_int8) + ',' + str(peak_gops_int8) + '}',
        })
        chart.set_title({
            'name': workload + ' ' + 'Mixed Precision Roofline',
            'name_font': {'size': 18},
        })
    chart.set_legend({
        'font': {'size': 12},
        'position': 'top',
    })
    chart.set_x_axis({
        'name': 'Intensity',
        'name_font': {'size': 12},
        'num_font': {'size': 11},
        'label_position': 'low',
        'min': 0.1,
        'log_base': 10,
        'crossing': '0.1',
    })
    chart.set_y_axis({
        'name': 'GFLOPS/s',
        'name_font': {'size': 12},
        'num_font': {'size': 11},
        'label_position': 'low',
        'min': 0.1,
        'log_base': 10,
        'crossing': '0.1',
    })
    conv_worksheet.insert_chart(1, 1, chart, {'x_scale': 2, 'y_scale': 2})
 
  if len(df) > 0 and not isSingleIter:
    conv_worksheet = workbook.get_worksheet_by_name('MKLDNN GEMMs')
    chart = workbook.add_chart({'type': 'scatter', 'subtype': 'straight'})
    start = 2 # first row is header, then ignore 1st data row (first call is always very slow)
    end = min(len(df), 1e6)  # excel can't show more than 1 million rows
    chart.add_series({
      # sheet name, start row, start col, end row, end col
      'name': workload + '_' + str(num_cores) + 'core_' + precision,
      'categories': ['MKLDNN GEMMs', start, df.columns.get_loc("intensity"), end, df.columns.get_loc("intensity")],
      'values': ['MKLDNN GEMMs', start, df.columns.get_loc("GFLOPS/s"), end, df.columns.get_loc("GFLOPS/s")],
      'line': {'none': True},
      'marker': {'type': 'automatic'},
    })
    if not isMixedPrecision:
        chart.add_series({
        'name': machine + '_' + str(num_cores) + 'core_' + precision,
        'categories': '={1e-100,' + str(inflection) + ',1e5}',
        'values': '={1e-100,' + str(peak_gops) + ',' + str(peak_gops) + '}',
        })
        chart.set_title({
            'name': workload + ' ' + precision + ' Roofline',
            'name_font': {'size': 18},
        })
    else:
        chart.add_series({
            'name': machine + '_' + str(num_cores) + 'core_' + 'fp32',
            'categories': '={1e-100,' + str(inflection_fp32) + ',1e5}',
            'values': '={1e-100,' + str(peak_gops_fp32) + ',' + str(peak_gops_fp32) + '}',
        })
        chart.add_series({
            'name': machine + '_' + str(num_cores) + 'core_' + 'int8',
            'categories': '={1e-100,' + str(inflection_int8) + ',1e5}',
            'values': '={1e-100,' + str(peak_gops_int8) + ',' + str(peak_gops_int8) + '}',
        })
        chart.set_title({
            'name': workload + ' ' + 'Mixed Precision Roofline',
            'name_font': {'size': 18},
        })
    chart.set_legend({
        'font': {'size': 12},
        'position': 'top',
    })
    chart.set_x_axis({
        'name': 'Intensity',
        'name_font': {'size': 12},
        'num_font': {'size': 11},
        'label_position': 'low',
        'min': 0.1,
        'log_base': 10,
        'crossing': '0.1',
    })
    chart.set_y_axis({
        'name': 'GFLOPS/s',
        'name_font': {'size': 12},
        'num_font': {'size': 11},
        'label_position': 'low',
        'min': 0.1,
        'log_base': 10,
        'crossing': '0.1',
    })
    conv_worksheet.insert_chart(1, 1, chart, {'x_scale': 2, 'y_scale': 2})
 
  if len(mkl_df) > 0 and 'intensity' in mkl_df and mkl_sheet_created and not isSingleIter:
    mkl_worksheet = workbook.get_worksheet_by_name('MKL')
    chart = workbook.add_chart({'type': 'scatter', 'subtype': 'straight'})
    start = 2 # first row is header, then ignore 1st data row (first call is always very slow)
    end = min(len(mkl_df), 1e6)  # excel can't show more than 1 million rows
    chart.add_series({
      # sheet name, start row, start col, end row, end col
      'name': workload + '_' + str(num_cores) + 'core_' + precision,
      'categories': ['MKL', start, mkl_df.columns.get_loc("intensity"), end, mkl_df.columns.get_loc("intensity")],
      'values': ['MKL', start, mkl_df.columns.get_loc("GFLOPS/s"), end, mkl_df.columns.get_loc("GFLOPS/s")],
      'line': {'none': True},
      'marker': {'type': 'automatic'},
    })
    chart.add_series({
      'name': machine + '_' + str(num_cores) + 'core_' + precision,
      'categories': '={1e-100,' + str(inflection) + ',1e5}',
      'values': '={1e-100,' + str(peak_gops) + ',' + str(peak_gops) + '}',
    })
    if not isMixedPrecision:
        chart.set_title({
            'name': workload + ' ' + precision + ' Roofline',
            'name_font': {'size': 18},
        })
        chart.set_legend({
            'font': {'size': 12},
            'position': 'top',
        })
    else:
        chart.add_series({
            'name': machine + str(num_cores) + 'core_' + 'fp32',
            'categories': '={1e-100,' + str(inflection_fp32) + ',1e5}',
            'values': '={1e-100,' + str(peak_gops_fp32) + ',' + str(peak_gops_fp32) + '}',
        })
        chart.add_series({
            'name': machine + str(num_cores) + 'core_' + 'int8',
            'categories': '={1e-100,' + str(inflection_int8) + ',1e5}',
            'values': '={1e-100,' + str(peak_gops_int8) + ',' + str(peak_gops_int8) + '}',
        })
        chart.set_title({
            'name': workload + ' ' + 'Mixed Precision Roofline',
            'name_font': {'size': 18},
        })
    chart.set_x_axis({
        'name': 'Intensity',
        'name_font': {'size': 12},
        'num_font': {'size': 11},
        'label_position': 'low',
        'min': 0.1,
        'log_base': 10,
        'crossing': '0.1',
    })
    chart.set_y_axis({
        'name': 'GFLOPS/s',
        'name_font': {'size': 12},
        'num_font': {'size': 11},
        'label_position': 'low',
        'min': 0.1,
        'log_base': 10,
        'crossing': '0.1',
    })
    mkl_worksheet.insert_chart(1, 1, chart, {'x_scale': 2, 'y_scale': 2})
 
  writer.save()
  print("\tFinished", workload, precision)



# compare across workloads
def cross_workload():
  print("\nProcessing cross-workload comparison")
  if not isSingleIter:
    output = resultdir + '/results/cross_workload_comparison.xlsx'
  else:
    output = resultdir + '/results_singleIter/cross_workload_comparison_singleIter.xlsx'
  writer = pd.ExcelWriter(output, engine='xlsxwriter')
  
  # for some reason converting manager list directly to df doesn't work so need to iterate on it
  all_primitives_df = pd.DataFrame()
  for item in all_primitives:
    all_primitives_df = all_primitives_df.append(item, ignore_index=True)
  all_primitives_df = all_primitives_df.set_index('workload').transpose().sort_index(axis=1)
  #print(all_primitives_df.index.values)
  new_idx = all_primitives_df.index.to_list()
  #print("new_idx ",new_idx)
  new_idx.remove('other')
  #print("new_idx ",new_idx)
  new_idx.append('other')
  #print("new_idx ",new_idx)
  all_primitives_df = all_primitives_df.reindex(new_idx)
  #print(all_primitives_df.index.values)
  all_primitives_df.to_excel(writer, sheet_name='Primitives')
  
  all_kernels_time_df = pd.DataFrame()
  for item in all_kernels_time:
    all_kernels_time_df = all_kernels_time_df.append(item, ignore_index=True)
  all_kernels_time_df = all_kernels_time_df.set_index('workload').transpose().sort_index(axis=1)  # index on workload, then transpose and sort by index
  all_kernels_time_df = all_kernels_time_df.iloc[all_kernels_time_df.isnull().sum(axis=1).mul(-1).argsort()]  # sort rows by commonality among workloads
  all_kernels_time_df = all_kernels_time_df.iloc[::-1]  # reverse order so "most common" is at top
  all_kernels_time_df.to_excel(writer, sheet_name='Kernel % Time')
  
  # pull out top 5 kernels for each WL
  # this code is a nightmare but it's all I could get to work to merge dataframes
  top5_df = pd.DataFrame()
  for row in all_kernels_time:
    # save workload_precision and delete from dict
    workload_precision = row['workload']
    del row['workload']
    # sort and pull out top 5 kernels by time
    top5_time = {k: v for k, v in sorted(row.items(), key=lambda item: item[1], reverse=True)[:min(5,len(row))]}
    # pull out efficiencies for these kernels
    # first find row for this workload
    workload_efficiencies = {k:v for (k,v) in [row1 for row1 in all_kernels_eff if row1['workload'] == workload_precision][0].items()}
    for k,v in top5_time.items():
      one_kernel = pd.DataFrame([[v, workload_efficiencies[k]]], columns=[workload_precision + '_time', workload_precision + '_eff'], index=[k])
      if k in top5_df.index:
        for index,row in one_kernel.iterrows():
          for key,value in row.items():
            if key not in top5_df:
              top5_df[key] = None
            top5_df.at[k, key] = value
      else:
        top5_df = top5_df.append(one_kernel, sort=False)
  top5_df.sort_index(axis=1).to_excel(writer, sheet_name='Top 5 Kernels')
  
  all_kernels_eff_df = pd.DataFrame()
  for item in all_kernels_eff:
    all_kernels_eff_df = all_kernels_eff_df.append(item, ignore_index=True)
  all_kernels_eff_df = all_kernels_eff_df.set_index('workload').transpose().sort_index(axis=1)
  all_kernels_eff_df = all_kernels_eff_df.iloc[all_kernels_eff_df.isnull().sum(axis=1).mul(-1).argsort()]
  all_kernels_eff_df = all_kernels_eff_df.iloc[::-1]
  all_kernels_eff_df.to_excel(writer, sheet_name='Kernel % Efficiency')
  
  all_timings_df = pd.DataFrame()
  for item in all_timings:
    all_timings_df = all_timings_df.append(item, ignore_index=True)
  all_timings_df = all_timings_df.set_index('workload').transpose().sort_index(axis=1)
  #all_timings_df = all_timings_df.set_index('workload').transpose().sort_values(by=['tmul_workload_speedup_%'], ascending=False, axis=1)
  all_timings_df.to_excel(writer, sheet_name='Stats')
  
  # add primitive chart
  workbook = writer.book
  worksheet = workbook.get_worksheet_by_name('Primitives')
  chart = workbook.add_chart({'type': 'column', 'subtype': 'stacked'})
  i = 0
  for index,row in all_primitives_df.iterrows():
    chart.add_series({
      # sheet name, start row, start col, end row, end col
      'name': index,
      'categories': ['Primitives', 0, 1, 0, row.size],
      'values': ['Primitives', i+1, 1, i+1, row.size],
    })
    i += 1
  chart.set_title({
      'name': 'MKLDNN Primitive Time',
      'name_font': {'size': 18},
  })
  chart.set_legend({
      'font': {'size': 12},
      'position': 'top',
  })
  chart.set_x_axis({
      'name_font': {'size': 12},
      'num_font': {'size': 11},
      'label_position': 'low',
  })
  chart.set_y_axis({
      'name': '% Time',
      'name_font': {'size': 12},
      'num_font': {'size': 11},
      'label_position': 'low',
      'max': 100,
  })
  worksheet.insert_chart(len(all_primitives_df)+2, 0, chart, {'x_scale': 2, 'y_scale': 2})
  
  # add tmul speedup chart
  #worksheet = workbook.get_worksheet_by_name('Stats')
  #chart = workbook.add_chart({'type': 'line'})
  #chart.add_series({
    # sheet name, start row, start col, end row, end col
  #  'name': 'TMUL Workload % Speedup',
  #  'categories': ['Stats', 0, 1, 0, len(all_timings_df.columns)],
  #  'values': ['Stats', all_timings_df.index.get_loc('tmul_workload_speedup_%')+1, 1, all_timings_df.index.get_loc('tmul_workload_speedup_%')+1, len(all_timings_df.columns)],
  #})
  #chart.set_title({
  #    'name': 'MKLDNN TMUL Workload % Speedup',
  #    'name_font': {'size': 18},
  #})
  #chart.set_legend({
  #    'none': True,
  #})
  #chart.set_x_axis({
  #    'name_font': {'size': 12},
  #    'num_font': {'size': 11},
  #    'label_position': 'low',
  #})
  #chart.set_y_axis({
  #    'name': '% Speedup',
  #    'name_font': {'size': 12},
  #    'num_font': {'size': 11},
  #    'label_position': 'low',
  #})
  #worksheet.insert_chart(len(all_timings_df)+2, 0, chart, {'x_scale': 2, 'y_scale': 2})
  
  # add weighted efficiency chart
  chart = workbook.add_chart({'type': 'column'})
  chart.add_series({
    # sheet name, start row, start col, end row, end col
    'name': 'Gemm Average Weighted Efficiency',
    'categories': ['Stats', 0, 1, 0, len(all_timings_df.columns)],
    'values': ['Stats', all_timings_df.index.get_loc('avg_weighted_efficiency_%')+1, 1, all_timings_df.index.get_loc('avg_weighted_efficiency_%')+1, len(all_timings_df.columns)],
  })
  chart.set_title({
      'name': 'Gemm Weighted % Efficiency',
      'name_font': {'size': 18},
  })
  chart.set_legend({
      'none': True,
  })
  chart.set_x_axis({
      'name_font': {'size': 12},
      'num_font': {'size': 11},
      'label_position': 'low',
  })
  chart.set_y_axis({
      'name': 'Efficiency (%)',
      'name_font': {'size': 12},
      'num_font': {'size': 11},
      'label_position': 'low',
  })
  worksheet.insert_chart(len(all_timings_df)+32, 0, chart, {'x_scale': 2, 'y_scale': 2})
  
  writer.save()



### MAIN ###
'''
for workload_dir in glob(topdir + '/*/'):
  print("workload_dir " + workload_dir)
  workload = workload_dir.split('/')[-2]
  print("workload " + workload)
  for precision_dir in glob(workload_dir + '/*/'):
    print("precision_dir " + precision_dir)
    precision = 'float32' if 'float32' in precision_dir else 'int8'
    print("precision " + precision)

#    if 'dcgan' not in workload and 'unet' not in workload:
#      continue
#    if 'inception_resnet_v2' not in workload:
#      continue
#    if 'ssd_vgg' in workload or 'fasterrcnn' in workload:
#      continue

#    if 'wide' in workload:
#      continue

    if 'densenet' not in workload:
      continue

    for namespace_dir in glob(precision_dir + '/0/*/'):
      print ("namespace_dir " + namespace_dir)
      log = namespace_dir + '/logs/console.log'

      if 'aibt-fasterrcnn-1-1-mkldnn-int8-1-fmx079-mkldnnverbose1' in log:
        continue  # ignore old run of fasterrcnn with fewer iterations

      if not os.path.exists(log):
        print("ERROR, can't find %s"%(log))
      else:
        print("Found", workload, precision, log)
        workload_list.append({'workload': workload, 'precision': precision, 'log': log, 'dir': namespace_dir})
'''
#new_list = workload_list
#new_list = {'workload': 'resnet50_v15'}
#print ("new_list")
#print(new_list)
#new_list = []
#include = False
#for item in workload_list:
#  if 'wide_and_deep' in item['workload']:
#    include = True
#  if include == True:
#    new_list.append(item)
#new_list = {}
#print("\nProcessing %d workloads"%(len(new_list)))

foundFiles = False
workload_list = []
for directory in os.listdir(topdir):
    #print("directory")
    #print(directory)
    if 'result' in directory:
        continue
    if os.path.isdir(topdir + '/' + directory):
        for filename in os.listdir(topdir + '/' + directory):

            if (not isSingleIter and 'singleIter' not in filename) or (isSingleIter and 'singleIter' in filename):
                foundFiles = True
                print("directory="+directory)
                print("filename1="+filename)
                if not isSingleIter:
                    #workload = directory.split('_')[0] + '-' + filename.rsplit('_',1)[1].split('.')[0]
                    workload = directory + '_' + 'ins0' #filename.rsplit('_',1)[1].split('.')[0]
                else:
                    #workload = directory.split('_')[0] + '-' + filename.split('_')[-2]
                    workload = directory + '_' + filename.split('_')[-2]
                print("workload"+workload)
                precision = workload.split('-')[2]
                print(precision)
                log = topdir + '/' + directory + '/' + filename
                if not isSingleIter:
                    num_cores = int(filename.split('_')[-2].split('c')[0])  # how many cores
                else:
                    num_cores = int(filename.split('_')[-3].split('c')[0])  # how many cores
                workload_list.append({'workload': workload, 'precision': precision, 'log': log, 'num_cores': num_cores})

                #dram_channels = 12 if num_cores > 28 else 6  # number of dram channels available to workload
                #peak_gbps = 2.933 * 8 * dram_channels  # based on dram freq

#print(workload_list)

pool = Pool(parallel_processes)
pool.map(process_workloads, workload_list)
pool.close()
if foundFiles: 
    cross_workload()
else:
    print("\nNo files found")
print("\nDone")
'''
pool = Pool(parallel_processes)
pool.map(process_workloads, new_list)
pool.close()
#cross_workload()
print("\nDone")

'''
