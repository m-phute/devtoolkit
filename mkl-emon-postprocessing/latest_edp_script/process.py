import os
import re
import log
import math
import pandas as pd


# Necessary to not truncate column data in pandas
# Used for long strings (such as HTML links) and floats (such as timestamps)
pd.set_option('display.max_colwidth', -1)


class Process():
  from _convert import convert_to_csv, convert_from_edp, add_entry_info
  from _aggregate import aggregate
  from _metrics import get_raw_data, get_python_formula, eval_row, evaluate_metrics_row, get_FMA_mult, calculate_metrics
  from _filter import filter
  from _aibt import aibt_login, aibt_search, match_aibt_timestamp
  from _excel import create_excel, format_core_freq, add_chart, get_baseline_precision, try_avg, filter_df, calc_scaling, calc_pct_change_per_val, create_filter_summary, combine_and_summarize


  def __init__(self, overwrite, generate_per_core, verbose, results_dir, intermediate, aibt, logging, disable_averaging):
    self.OVERWRITE = overwrite
    self.GENERATE_PER_CORE = generate_per_core
    self.VERBOSE = verbose
    self.INTERMEDIATE = intermediate
    self.AIBT = aibt
    self.results_dir = results_dir
    self.logging = logging
    self.tokens = [None, None]
    self.DISABLE_AVERAGING = disable_averaging

  def isfloat(self, num):
    try:
        a = float(num)
        return not math.isnan(a)
    except ValueError:
        return False


  def tryint(self, s):
    try:
        return int(s)
    except ValueError:
        return s


  def alphanum_key(self, s):
    """ Turn a string into a list of string and number chunks.
        "z23a" -> ["z", 23, "a"]
    """
    return [ self.tryint(c) for c in re.split('([0-9]+)', s) ]


  def get_cpu(self, cpu_family):
    if 'Skylake' in cpu_family:
        return 'skx'
    elif 'Broadwell' in cpu_family:
        return 'bdx'
    elif 'Cascadelake' in cpu_family:
        return 'clx'
    elif 'AMD' in cpu_family:
        return 'amd'
    else:
        return 'unknown'


  def parse_system_info(self, file):
    # (if there is only one socket package count doesn't seem to be explicitely stated)
    system_info = {
        'system.sockets.count': 2,
        'system.socket_count': 2,
        'system.sockets[0].cores.count': 0,
        'system.sockets[0].cpus.count': 0,
        'system.sockets[0][0].size': 0,
        'system.sockets[1].cores.count': 0,
        'system.sockets[1].cpus.count': 0,
        'system.sockets[1][0].size': 0,
        'system.cha_count/system.socket_count': 0,
        'DRAM freq': 0,
        'dram_channels': 0
    }
    for line in file:
        if 'TSC Freq' in line:
            m = re.search('\D(\d+\.\d*)', line)
            system_info['system.tsc_freq'] = float(m.group(1)) * 1e6
        if 'cpu_family' in line:
            line = line.replace('NaN','').rstrip()
            m = re.search('\.+ (.*)', line)
            system_info['cpu_family'] = m.group(1)
            system_info['cpu_short'] = self.get_cpu(m.group(1))
        elif 'Number of Packages' in line:
            m = re.search('\D(\d+)', line)
            system_info['system.sockets.count'] = float(m.group(1))
            system_info['system.socket_count'] = float(m.group(1))
        elif 'Cores Per Package' in line:
            m = re.search('\D(\d+)', line)
            for j in range(int(system_info['system.sockets.count'])):
                system_info['system.sockets[' + str(j) + '].cores.count'] = m.group(1)
                system_info['system.sockets[' + str(j) + '].cpus.count'] = m.group(1)
                system_info['system.cha_count/system.socket_count'] = m.group(1)
        elif 'Threads Per Core' in line:
            m = re.search('\D(\d+)', line)
            # Seems we are only using [0][0] in EDP, so this iteration maynot be necessary
            for j in range(int(system_info['system.sockets.count'])):
                system_info['system.sockets[' + str(j) +'][0].size'] = m.group(1)
        elif 'number_of_online_processors' in line:
            m = re.search('\D(\d+)', line)
            system_info['number_of_online_processors'] = float(m.group(1))
        elif 'Total Number of Ranks' in line:  # on this Channel
            system_info['dram_channels'] = system_info['dram_channels'] + 1
        elif 'CPU Freq (detected)' in line:
            m = re.search('\D(\d+\.\d*)', line)
            system_info['core freq'] = float(m.group(1)) / 1000.0
        elif 'UFS Freq (limit)' in line:
            m = re.search('\D(\d+\.\d*)', line)
            system_info['uncore freq'] = float(m.group(1)) / 1000.0
        elif 'Speed' in line:
            m = re.search('\D(\d+)MHz', line)
            system_info['DRAM freq'] = m.group(1)

    # assume dram channels & speed if that info isn't in emonv
    if system_info['dram_channels'] == 0:
        if 'cpu_short' in system_info:
            if system_info['cpu_short'] == 'skx':
                system_info['dram_channels'] = 12
            elif system_info['cpu_short'] == 'bdx':
                system_info['dram_channels'] = 8
            elif system_info['cpu_short'] == 'clx':
                system_info['dram_channels'] = 12
            elif system_info['cpu_short'] == 'amd':
                system_info['dram_channels'] = 16
        else:
            system_info['dram_channels'] = 1

    if system_info['DRAM freq'] == 0:
        if 'cpu_short' in system_info:
            if system_info['cpu_short'] == 'skx':
                system_info['DRAM freq'] = 2666
            elif system_info['cpu_short'] == 'bdx':
                system_info['DRAM freq'] = 2133
            elif system_info['cpu_short'] == 'clx':
                system_info['DRAM freq'] = 2933
            elif system_info['cpu_short'] == 'amd':
                system_info['DRAM freq'] = 2666
        else:
            system_info['DRAM freq'] = 2666

    return system_info




