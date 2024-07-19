import os
import log
import re
import time
import sys
import pandas as pd
import xml.etree.ElementTree as ET
import copy


metric_dir_older_edp = "./"
metric_dir_latest_edp = "./"
metrics_files_older_edp = {
    'skx': metric_dir_older_edp + 'SKX-2S/skx-2s.xml',
    'bdx': metric_dir_older_edp + 'BDX-EP/bdx-ep_w_FLOPS_fixed.xml',
    'clx': metric_dir_older_edp + './xmls/clx-2s.xml',
    'amd': metric_dir_older_edp + './xmls/zen2-rome-2s.xml',
}
metrics_files_latest_edp = {
    'skx': metric_dir_latest_edp + 'Skylake/SKX-2S/skx-2s.xml',
    'bdx': metric_dir_latest_edp + 'Broadwell/BDX-EP/bdx-ep.xml',
    'clx': metric_dir_latest_edp + './xmls/clx-2s.xml',
    'amd': metric_dir_latest_edp + './xmls/zen2-rome-2s.xml',
}


def get_raw_data(self, file_name, phase_start_stamp, phase_stop_stamp):  
    raw_data = pd.read_csv(open(file_name, 'rb'), index_col=0)

    if phase_start_stamp is not None and phase_stop_stamp is not None:
        raw_data = raw_data[raw_data['unix_Timestamp'].map(lambda x: x > phase_start_stamp and x < phase_stop_stamp)]
    
    return raw_data


def get_python_formula(self, formula):

    # Replace '?' with python ternary operator
    while '?' in formula:

        # m = re.search(r'([^\?]+)\?([^:]+):(.*)', formula)
        # Above formula does not support nesting
        # Using (.*) for the first group leads looking for
        # innermost ternary operator
        m = re.search(r'(.*)\?([^:]+):(.*)', formula)

        # Condition
        paran_stack = []
        paran_matches = list(re.finditer("\(|\)", m.group(1)))
        start_replace = None
        for m1 in reversed(paran_matches):
            if m1.group(0) == ")":
                 paran_stack.append(m1.start())
            else:
                paran_stack.pop()
                if not paran_stack:
                    condition = m.group(1)[m1.start():]
                    start_replace = m.start(1) + m1.start()
                    break

        # True part
        true_part = m.group(2)

        # False part
        paran_matches = list(re.finditer("\(|\)", m.group(3)))
        end_replace = None
        for m1 in reversed(paran_matches):
            if m1.group(0) == ")":
                 paran_stack.append(m1.start())
            else:
                 paran_stack.pop()
        if paran_stack:
            end_replace = paran_stack.pop()
            false_part = m.group(3)[:end_replace]
            end_replace += m.start(3)

        if end_replace is None or start_replace is None:
            self.logging.log("error", "Error in formula evaluation")
            return None

        formula = formula[:start_replace] + "(" + true_part + ") if (" + condition + ") else (" + false_part + ")" + formula[end_replace:]

    # Replace '.min' directives with python compatible ones
    while '.min' in formula:

        m = re.search(r'(\.min)', formula)
        ss = formula[0:m.start(1)]
        bracket_matches = list(re.finditer("\[|\]", ss))
        replace_end = m.start(1) + 4
        bracket_stack = []
        for m1 in reversed(bracket_matches):
            if m1.group(0) == "]":
                bracket_stack.append(m1.start())
            else:
                bracket_stack.pop()
                if not bracket_stack:
                    ss1 = ss[m1.start()+1:-1]
                    replace_start = m.start(1) + m1.start()
                    break

        formula = formula[:m1.start()] + "min(" + ss1 + ")" + formula[replace_end:]

    return formula
    

# handles if there is a divide by zero in an equation
def eval_row(self, formula, row):
    try:
        return eval(formula)
    except Exception:
        return None
    
    
def evaluate_metrics_row(self, raw_data, metrics_definition_path, out_file):
    if raw_data is None:
        return None
    
    # read in xml and copy raw emon data
    tree = ET.parse(metrics_definition_path)
    root = tree.getroot()
    new_data = copy.deepcopy(raw_data)

    for child in root:
        if self.VERBOSE:
            print("\t", child.attrib['name'])
        
        # get formula
        all_counters = True
        formula = ""
        for grandchild in child:
            if grandchild.tag == 'formula' and 'socket' not in grandchild.keys():
                formula = self.get_python_formula(grandchild.text)
                #print(formula)  # original formula with aliases
                break
                     
        # replace alias' with dataframe rows to evaluate
        for grandchild in child:
            if grandchild.tag == 'event':
                if grandchild.text not in list(new_data):
                    if self.VERBOSE:
                        self.logging.log("warning", "Continuing..." + grandchild.text + " not found")
                    all_counters = False
                    break
                else:
                    # the regex character '\b' is a word boundary, so it will only replace an alias surrounded by non-letters
                    # this covers the case where you want to replace an alias 'a' but there is also the word 'threads' in the formula
                    formula = re.sub(r'\b' + grandchild.attrib['alias'] + r'\b', "row['" + grandchild.text + "']", formula)
            elif grandchild.tag == 'constant':
                try:
                    float(grandchild.text)
                    formula = re.sub(r'\b' + grandchild.attrib['alias'] + r'\b', grandchild.text, formula)
                except Exception:
                    if grandchild.text not in list(new_data):
                        if self.VERBOSE:
                            self.logging.log("warning", "Continuing..." + grandchild.text + " not found")
                        all_counters = False
                        break
                    else:
                        formula = re.sub(r'\b' + grandchild.attrib['alias'] + r'\b', "row['" + grandchild.text + "']", formula)

        if not all_counters:
            new_data[child.attrib['name']] = None
        else:
            try:
                new_data[child.attrib['name']] = new_data.apply(lambda row: self.eval_row(formula, row), axis=1)
            except:
                self.logging.log("warning", "Problem in formula evaluation: " + child.attrib['name'] + "\nFormula: " + formula) # new formula with column names
                return None

    #new_data.to_csv(out_file)
    return new_data


def get_FMA_mult(self, row):
    if 'cpu_short' in row:
        if row['cpu_short'] == 'skx':
            return (8*2*2) * 2
        elif row['cpu_short'] == 'clx':
            return (8*2*2) * 2
        elif row['cpu_short'] == 'bdx':
            return (4*2*2) * 2
        else: # same as SKX
            return (8*2*2) * 2
    
    else:  # assume SKX
        return (8*2*2) * 2


def calculate_metrics(self, entry):
    #print("Calculating XML Metrics...")
    run = entry['name']
    emon_dir = entry['emon_dir']
    new_granularity_sec = entry['agg_secs']
    start_stamp = None
    stop_stamp = None
    start_time = time.time()
    
    #max_upi = 10.4 * 12 * 8  # GB/s, NEEDS TO BE CONFIRMED
   
    if self.INTERMEDIATE == True:
        infile = self.results_dir + "/workloads/" + run + "/%s_emon_%.3fsec.csv"%(run, new_granularity_sec)
        outfile = self.results_dir + "/workloads/" + run + "/%s_emon_%.3fsec_metrics.csv"%(run, new_granularity_sec)
    else:
        infile = emon_dir + "/" + run + "_emon_%.3fsec.csv"%(new_granularity_sec)
        outfile = emon_dir + "/" + run + "_emon_%.3fsec_metrics.csv"%(new_granularity_sec)
 
    if os.path.isfile(outfile):
        if self.OVERWRITE == False:
            return True
        else:
            os.remove(outfile)
    
    if not os.path.isfile(infile):
        self.logging.log("warning,", "Can't find %s to add metrics"%(infile))
        if os.path.isfile(outfile):
            os.remove(outfile)
        return False
    
    
    try:
        raw_data = self.get_raw_data(infile, start_stamp, stop_stamp)
        if 'metrics' in entry and '.xml' in entry['metrics'] and os.path.isfile(entry['metrics']) == True:  # someone can specify full path if they want (and they should)
          add_more_metrics = False  # assume for now if they specify full path that xml has all the metrics they need
          raw_data['metrics_file'] = entry['metrics']
          if 'cpu_short' in raw_data:
            cpu_short = raw_data['cpu_short'].values[0]
          else:
            self.logging.log("warning", "Can't determine cpu family for %s, assuming SKX!"%(run))
            raw_data['cpu_short'] = 'skx'
        else: #if user doesn't specify, assume its our older metrics files
          add_more_metrics = True
          if 'cpu_short' in raw_data:
            cpu_short = raw_data['cpu_short'].values[0]
            if cpu_short == 'skx':
              if 'UNC_CHA_CLOCKTICKS' in raw_data:
                raw_data['metrics_file'] = metric_dir_older_edp + 'SKX-2S/skx-2s_cha.xml'
              else:
                raw_data['metrics_file'] = metric_dir_older_edp + 'SKX-2S/' + entry['metrics']
            elif cpu_short == 'bdx' or cpu_short == 'clx' or cpu_short == 'amd':
              raw_data['metrics_file'] = metrics_files_older_edp[cpu_short]
            else:
              self.logging.log("warning", "cpu_family for %s is %s, not adding metrics!"%(run, cpu_short))
              raw_data.to_csv(outfile)
              return False
          else:
            self.logging.log("warning", "Can't determine cpu family for %s, assuming SKX!"%(run))
            raw_data['cpu_short'] = 'skx'
            raw_data['metrics_file'] = metric_dir_older_edp + 'SKX-2S/' + entry['metrics']
        
        metric_file = raw_data['metrics_file'].values[0]
        self.logging.log("info", "Calculating metrics for %s using %s..."%(run, metric_file))
        new_data = self.evaluate_metrics_row(raw_data, metric_file, outfile)
    except Exception as e:
        self.logging.log("error", "Exception for %s: %s: %s"%(run, sys.exc_info()[0], e))
        return False
  
 
    if add_more_metrics == True: 
      #add some extra non-xml metrics
      pcie_3_x8_max_bw = 7.88e9  # B/s
      #new_data['cum_duration'] = new_data['duration'].cumsum()  # added in _convert module now for filtering
      try:
        new_data['cores available'] = new_data['system.sockets[0].cores.count'] + new_data['system.sockets[1].cores.count']
        if cpu_short == 'amd':
            #new_data['NUMA %local'] = new_data['metric_NUMA %_Reads addressed to local DRAM/Die'] / (new_data['metric_NUMA %_Reads addressed to local DRAM/Die'] + new_data['metric_NUMA %_Reads addressed to remote DRAM/Die'])
            new_data['NUMA %local'] = new_data['metric_NUMA %_Reads addressed to local DRAM/Die']
            new_data['L3 MPKI'] = new_data['metric_L3 misses per instr'] * 1000
            new_data['L2 MPKI'] = new_data['metric_L2 Demand Read (dataRd+rfo) MPI '] * 1000
            new_data['metric_memory bandwidth read (MB/sec)'] = 0
            new_data['metric_memory bandwidth write (MB/sec)'] = 0
            new_data['DDR BW/core (GB/s)'] = (new_data['metric_memory bandwidth read (MB/sec)'] + new_data['metric_memory bandwidth write (MB/sec)']) / new_data['cores used'] / 1000
            new_data['Remote hitm (%LLC miss)'] = 0
            new_data['DDR Rd Ratio'] = new_data['metric_memory bandwidth read (MB/sec)'] / new_data['metric_memory bandwidth write (MB/sec)']
            new_data['IO BW (MB/s)'] = 0
            new_data['PCIE 3.0 x8 Util'] = 0
            new_data['CPU Utilization used threads %'] = new_data.apply(lambda row: min(100.0, row['metric_CPU utilization %'] * (row['cores available'] * 2 / row['cores used'])), axis=1)
            new_data['metric_UPI Transmit utilization_% (includes control)'] = 0
            new_data['metric_TMAM_Frontend_Bound(%)'] = 0
            new_data['metric_TMAM_Backend_bound(%)'] = 0
            new_data['metric_TMAM_Bad_Speculation(%)'] = 0
            new_data['metric_TMAM_Retiring(%)'] = 0
            new_data['Roofline Elbow'] = 0
            new_data['Theoretical Peak GFLOPS/s'] = 0
            new_data['metric_GFLOPS/s'] = 0
            new_data['metric_Arithmetic Intensity'] = 0
        else:
            new_data['DRAM Bytes'] = (new_data['UNC_M_CAS_COUNT.RD'] + new_data['UNC_M_CAS_COUNT.WR']) * 64.0
            new_data['DDR BW/core (GB/s)'] = (new_data['metric_memory bandwidth read (MB/sec)'] + new_data['metric_memory bandwidth write (MB/sec)']) / new_data['cores used'] / 1000
            new_data['DDR Rd Ratio'] = new_data['UNC_M_CAS_COUNT.RD'] / new_data['UNC_M_CAS_COUNT.WR']
            new_data['CPU Utilization used threads %'] = new_data.apply(lambda row: min(100.0, row['metric_CPU utilization %'] * (row['cores available'] * 2 / row['cores used'])), axis=1)
            new_data['Theoretical Peak DRAM GB/s'] = new_data['DRAM freq'] * 8 * new_data['dram_channels'] / 1000
            try:
                new_data['Theoretical Peak GFLOPS/s'] = new_data.apply(lambda row: (min(row['cores available'], row['cores used']) * pd.to_numeric(row['core freq']) * self.get_FMA_mult(row)), axis=1)
            except Exception:
                new_data['Theoretical Peak GFLOPS/s'] = new_data.apply(lambda row: (min(row['cores available'], row['cores used']) * row['system.tsc_freq'] / 1e9 * self.get_FMA_mult(row)), axis=1)
            new_data['Roofline Elbow'] = new_data['Theoretical Peak GFLOPS/s'] / new_data['Theoretical Peak DRAM GB/s']
            
            if 'memory' not in entry['metrics']:  # flops or default or proxy or tmam
                new_data['GFLOPS/s/core'] = new_data['metric_GFLOPS/s'] / new_data['cores used']
                new_data['FP Utilization %'] = new_data['metric_GFLOPS/s'] / new_data['Theoretical Peak GFLOPS/s'] * 100.0
                new_data['Achievable Peak GFLOPS/s'] = new_data.apply(lambda row: min(row['Theoretical Peak GFLOPS/s'], row['Theoretical Peak DRAM GB/s'] * row['metric_Arithmetic Intensity']), axis=1)
                new_data['FP Efficiency %'] = new_data['metric_GFLOPS/s'] / new_data['Achievable Peak GFLOPS/s'] * 100.0
                if 'flops' not in entry['metrics']:  # default or proxy or tmam
                    #new_data['NUMA %local'] = new_data['metric_NUMA %_Reads addressed to local DRAM'] / (new_data['metric_NUMA %_Reads addressed to local DRAM'] +                                           new_data['metric_NUMA %_Reads addressed to remote DRAM'])
                    new_data['NUMA %local'] = new_data['metric_NUMA %_Reads addressed to local DRAM']
                    new_data['IO BW (MB/s)'] = (new_data['metric_IO_bandwidth_disk_or_network_writes (MB/sec)'] + new_data['metric_IO_bandwidth_disk_or_network_reads (MB/sec)'])
                    new_data['PCIE 3.0 x8 Util %'] = new_data['IO BW (MB/s)'] * 1e6 / pcie_3_x8_max_bw * 100
                    if cpu_short == 'bdx':
                        new_data['L3 MPKI'] = new_data['MEM_LOAD_UOPS_RETIRED.L3_MISS'] / new_data['INST_RETIRED.ANY'] * 1000
                        new_data['L2 MPKI'] = new_data['MEM_LOAD_UOPS_RETIRED.L2_MISS'] / new_data['INST_RETIRED.ANY'] * 1000
                        new_data['Remote hitm (%LLC miss)'] = (new_data['OFFCORE_RESPONSE:request=ALL_READS:response=LLC_MISS.REMOTE_HITM'] / (new_data['OFFCORE_RESPONSE:request=ALL_READS:response=LLC_MISS.REMOTE_HITM'] + new_data['MEM_LOAD_UOPS_RETIRED.L3_MISS'])) * 100.0
                    else:
                        new_data['L3 MPKI'] = new_data['MEM_LOAD_RETIRED.L3_MISS'] / new_data['INST_RETIRED.ANY'] * 1000 if 'MEM_LOAD_RETIRED.L3_MISS' in new_data else None
                        new_data['L2 MPKI'] = new_data['MEM_LOAD_RETIRED.L2_MISS'] / new_data['INST_RETIRED.ANY'] * 1000 if 'MEM_LOAD_RETIRED.L2_MISS' in new_data else None
                        new_data['Remote hitm (%LLC miss)'] = (new_data['OFFCORE_RESPONSE:request=ALL_READS:response=L3_MISS.REMOTE_HITM'] / (new_data['OFFCORE_RESPONSE:request=ALL_READS:response=L3_MISS.REMOTE_HITM'] + new_data['MEM_LOAD_RETIRED.L3_MISS'])) * 100.0 if 'OFFCORE_RESPONSE:request=ALL_READS:response=L3_MISS.REMOTE_HITM' in new_data and 'MEM_LOAD_RETIRED.L3_MISS' in new_data else None
                    if 'proxy' not in entry['metrics'] and 'tmam' not in entry['metrics']:  # default
                        new_data['IO BW cache miss (MB/s)'] = (new_data['metric_IO_write cache miss(disk/network reads) bandwidth (MB/sec)'] + new_data['metric_IO_read cache miss(disk/network writes) bandwidth (MB/sec)']) if 'metric_IO_write cache miss(disk/network reads) bandwidth (MB/sec)' in new_data and 'metric_IO_read cache miss(disk/network writes) bandwidth (MB/sec)' in new_data else None
                        #new_data['metric_Average LLC data read (demand+prefetch) miss latency (in ns)'] = new_data['metric_Average LLC data read (demand+prefetch) miss latency (in UNCORE clk)'] / ((new_data['UNC_C_CLOCKTICKS'] / new_data['cores available']) / new_data['duration']) * 1e9
                        #new_data['metric_Average LLC data read (demand+prefetch) miss latency for LOCAL requests (in ns)'] = new_data['metric_Average LLC data read (demand+prefetch) miss latency  for LOCAL requests (in UNCORE clk)'] / ((new_data['UNC_C_CLOCKTICKS'] / new_data['cores available']) / new_data['duration']) * 1e9
                        #new_data['metric_Average LLC data read (demand+prefetch) miss latency for REMOTE requests (in ns)'] = new_data['metric_Average LLC data read (demand+prefetch) miss latency  for REMOTE requests (in UNCORE clk)'] / ((new_data['UNC_C_CLOCKTICKS'] / new_data['cores available']) / new_data['duration']) * 1e9
                        new_data['BACPI'] = new_data['BACLEARS.ANY'] / new_data['INST_RETIRED.ANY'] if 'BACLEARS.ANY' in new_data else None
                        new_data['ABRPI'] = new_data['BR_INST_RETIRED.ALL_BRANCHES'] / new_data['INST_RETIRED.ANY'] if 'BR_INST_RETIRED.ALL_BRANCHES' in new_data else None
                        new_data['JECPI'] = new_data['BR_MISP_RETIRED.ALL_BRANCHES'] / new_data['INST_RETIRED.ANY'] if 'BR_MISP_RETIRED.ALL_BRANCHES' in new_data else None
                        if cpu_short == 'bdx':
                            new_data['DIVIDERPI'] = new_data['ARITH.FPU_DIV_ACTIVE'] / new_data['INST_RETIRED.ANY'] if 'ARITH.FPU_DIV_ACTIVE' in new_data else None
                        else:
                            new_data['DIVIDERPI'] = new_data['ARITH.DIVIDER_ACTIVE'] / new_data['INST_RETIRED.ANY'] if 'ARITH.DIVIDER_ACTIVE' in new_data else None
      except Exception as e:
        self.logging.log('warning', 'Unable to add some metrics ' + e)   
 
    # now that we have all the metrics, we can filter (allows auto filtering on derived columns)
    new_data['suggested_start'], new_data['suggested_start_confidence'], \
    new_data['suggested_stop'], new_data['suggested_stop_confidence'] = self.filter(entry, new_data)

    # attempt aibt matching
    new_data = self.aibt_search(new_data)

    # one-time: print start/stop timestamps
    #if new_data['suggested_start'].values[0] != new_data['suggested_stop'].values[0]:
    #  self.logging.log("nfo", "%s,%s,%s"%(entry['name'], new_data.iloc[new_data['suggested_start'].values[0]]['timestamp'], new_data.iloc[new_data['suggested_stop'].values[0]]['timestamp']))

    #save to file
    new_data.to_csv(outfile)

    self.logging.log("info", "Calculated metrics for %s in %d secs"%(run, time.time() - start_time))
    return True

