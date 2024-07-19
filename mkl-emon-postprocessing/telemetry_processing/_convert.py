import math
import os
import re
import log
import subprocess
import queue
import time
import pandas as pd
from datetime import datetime
from dateutil import parser


def add_entry_info(self, df, entry):
    #add all entry items to df
    for key,val in entry.items():
      if type(val) is not dict and type(val) is not list:  # don't need to add these
        df[key] = val

    tok = entry['name'].split('_')
    df['run'] = entry['name']
    df['cum_duration'] = df['duration'].cumsum()

    if len(tok) >= 7:
        df['workload'] = tok[0] if 'workload' not in entry else entry['workload']
        df['instances'] = int(tok[1].strip('i')) if 'instances' not in entry else entry['instances']
        df['cores per instance'] = int(tok[2].strip('cpi')) if 'cores per instance' not in entry else entry['cores per instance']
        df['core freq'] = str(tok[3].strip('cf').replace('de', 'default')) if 'core freq' not in entry else entry['core freq']
        df['uncore freq'] = str(tok[4].strip('uf').replace('de', 'default')) if 'uncore freq' not in entry else entry['uncore freq']
        df['DRAM freq'] = int(tok[5].strip('df')) if 'DRAM freq' not in entry else entry['DRAM freq']
        df['metrics'] = tok[6] if 'metrics' not in entry else entry['metrics']
    else:
        df['workload'] = df['run'] if 'workload' not in entry else entry['workload']
        df['instances'] = 1 if 'instances' not in entry else entry['instances']
        df['cores per instance'] = df['number_of_online_processors'] if 'cores per instance' not in entry else entry['cores per instance']
        df['core freq'] = 'default' if 'core freq' not in entry else entry['core freq']
        df['uncore freq'] = 'default' if 'uncore freq' not in entry else entry['uncore freq']
        df['metrics'] = 'default' if 'metrics' not in entry else entry['metrics']

    df['cores used'] = df['instances'] * df['cores per instance']
    df['performance'] = entry['perf'] if 'perf' in entry else entry['performance'] if 'performance' in entry else None 

    return df


def convert_from_edp(self, entry):
    run = entry['name']
    emon_dir = entry['emon_dir']
    infile = emon_dir + '/' + entry['edp_file']

    if self.INTERMEDIATE == True:
        if os.path.isdir(self.results_dir + "/workloads/" + run) != True:
            subprocess.check_output("mkdir %s"%(self.results_dir + "/workloads/" + run), shell=True)
        outfile = self.results_dir + "/workloads/" + run + "/" + run + "_emon_sum.csv"
    else:
        outfile = emon_dir + "/" + run + "_emon_sum.csv"

    start_time = time.time()
    
    if os.path.isfile(outfile):
        if self.OVERWRITE == False:
            return True
        else:
            os.remove(outfile)
    
    if not os.path.isfile(infile):
        self.logging.log("error", "Could not find %s to convert from edp"%(infile))
        return False
    else:
        self.logging.log("info", "Converting %s from edp to csv..."%(run))

    # parse emonv
    emonv = pd.read_excel(infile, sheet_name='emonV', index_col=None, header=None)
    sys_info = self.parse_system_info(emonv.to_string().splitlines())
    
    # parse emon
    data = pd.read_excel(infile, index_col=0, sheet_name='system view', na_values=['Infinity', 'NaN'])
    data = data.transpose()
    #drop_columns = [col for col in data.columns if 'metric_' in col]
    #data = data.drop(drop_columns, axis=1)  # remove calculated metrics (they're re-calculated later)
    data = data.loc[['aggregated']]  # get just avg
    data = data.reset_index(drop=True)
    
    # add emonv to emon
    for key,val in sys_info.items():
        data[key] = val
        
    # add other key columns
    data['duration'] = 1.0
    data['cum_duration'] = 1.0
    data['timestamp'] = None
    data['interval'] = 0
    data['TSC'] = data['number_of_online_processors'] * data['system.tsc_freq'] * data['duration']
    data['run'] = run
    data['workload'] = run
    data['instances'] = 1
    data['cores per instance'] = data['number_of_online_processors']
    data['cores used'] = data['number_of_online_processors']
    data['metrics'] = 'default'
    data['raw_emon'] = infile
    data['performance'] = entry['perf'] if 'perf' in entry else None
    data['suggested_start'] = 0
    data['suggested_stop'] = 0
    data['suggested_start_confidence'] = 'high'
    data['suggested_stop_confidence'] = 'high'
    
    # write to file
    data.to_csv(outfile, chunksize=1e6)

    self.logging.log("info", "Converting %s from edp to csv took %d secs"%(run, time.time() - start_time))
    return True


def convert_to_csv(self, entry):
    FMT = '%m/%d/%Y %H:%M:%S.%f'

    if 'edp_file' in entry:
        return self.convert_from_edp(entry)
    
    run = entry['name']
    emon_dir = entry['emon_dir']
    infile = None
    emonv_file = None
   
    if self.INTERMEDIATE == True:
        if os.path.isdir(self.results_dir + "/workloads/" + run) != True:
            subprocess.check_output("mkdir %s"%(self.results_dir + "/workloads/" + run), shell=True)
        outfile = self.results_dir + "/workloads/" + run + "/" + run + "_emon_sum.csv"
    else:
        outfile = emon_dir + "/" + run + "_emon_sum.csv"
 
    if os.path.isfile(outfile):
        if self.OVERWRITE == False:
            return True
        else:
            os.remove(outfile)
    
    possible_files = [emon_dir + '/emon.log', emon_dir + '/emon.dat', emon_dir + '/emon.txt']
    for possible_file in possible_files:
        if os.path.isfile(possible_file):
            infile = possible_file
            break
    if infile is None:
        self.logging.log("error", "Could not find emon.log/.dat/.txt in %s"%(emon_dir))
        return False
    
    possible_files = [emon_dir + '/../emonv.log', emon_dir + '/../emonv.dat', emon_dir + '/../emonv.txt',
                      emon_dir + '/../emon-v.log', emon_dir + '/../emon-v.dat', emon_dir + '/../emon-v.txt',
                      emon_dir + '/emonv.log', emon_dir + '/emonv.dat', emon_dir + '/emonv.txt',
                      emon_dir + '/emon-v.log', emon_dir + '/emon-v.dat', emon_dir + '/emon-v.txt']
    for possible_file in possible_files:
        if os.path.isfile(possible_file):
            emonv_file = possible_file
            break
    if emonv_file is None:
        self.logging.log("error", "Cound not find emonv in %s or its parent"%(emon_dir))
        return False
    
    self.logging.log("info", "Converting %s to csv..."%(run))

    emonv = open(emonv_file, 'r')
    sys_info = self.parse_system_info(emonv)
    emonv.close()

    output_bytes = subprocess.check_output("grep -e '-----' -e '=====' %s | wc -l"%(infile), shell=True)
    expected_samples = int(output_bytes.decode("utf-8"))
    #print("\tFound %d samples in file %s"%(expected_samples, infile))

    # initialize variables
    window_duration = 5  # secs to keep running avg
    window_size = 1e6  # intervals to keep running avg;starting value, will be updated once we know duration of interval
    instr_mean = None
    instr_stddev = None
    req_mean_mult = 2  # multiple that a data point must from avg to be considered significant
    instr_window = queue.Queue() # save last samples to try to find start/stop of workload
    #instr_window_sq = queue.Queue() # save last samples^2 to try to find start/stop of workload
    possible_starts = []
    possible_stops =  []
    sum_dict = {}
    per_core_dict = {}
    linenum = 0  # line number
    samplenum = -1  # sample number
    current_timestamp = None
    last_timestamp = None
    duration = None
    tsc = None
    timestamp = True  # flag to indicate next line is timestamp

    # read in txt
    start_time = time.time()
    with open(infile) as fp:
        #print("\tProcessing EMON samples...", end='', flush=True)
        for line in fp:
            linenum += 1
            if linenum < 3: #ignore first couple lines (EMON version and blank line)
                continue
            elif re.search('----------', line) or re.search('==========', line):  # break between samples (next line is timestamp)
                timestamp = True
            elif timestamp == True:  # save timestamp
                timestamp = False
                samplenum += 1
                last_timestamp = current_timestamp
                current_timestamp = line.strip()

                if re.search("real", current_timestamp): # end of samples
                    break

                if last_timestamp is not None:
                    duration = (datetime.strptime(current_timestamp, FMT) - datetime.strptime(last_timestamp, FMT)).total_seconds()
                    # count of total clocks for all cores for this interval
                    tsc = float(sys_info['number_of_online_processors']) * float(sys_info['system.tsc_freq']) * duration
                    # initialize queue to hold x secs of samples
                    if window_size == 1e6:
                        window_size = int(window_duration / duration)

                sum_dict[samplenum] = {'timestamp': parser.parse(current_timestamp), 'duration': duration, 'TSC': tsc, 'interval': samplenum, 'raw_emon': infile}
                sum_dict[samplenum] = {**sum_dict[samplenum], **sys_info}
                if self.GENERATE_PER_CORE:
                    per_core_dict[samplenum] = {'timestamp': parser.parse(current_timestamp), 'duration': duration, 'TSC': tsc, 'interval': samplenum}
                    per_core_dict[samplenum] = {**per_core_dict[samplenum], **sys_info}

            else:  # save samples
                sample = line.split()
                counter = sample[0]
                clocks = sample[1]
                sample.remove(counter)  # remove counter name
                sample.remove(clocks)  # remove count of clocks
                sample = [int(i.replace(',','')) for i in sample]  # convert to ints and remove commas
                total = sum(sample)
                #average = sum(sample)/len(sample)
                length = len(sample)

                #add to dfs
                sum_dict[samplenum][counter] = total
                if self.GENERATE_PER_CORE:
                    for i in range(0, length):
                        per_core_counter = "%s_%i"%(counter, i)
                        per_core_dict[samplenum][per_core_counter] = sample[i]

                # save possible start/stop samples
                #if counter == 'INST_RETIRED.ANY':
                #    # save instruction count
                #    if instr_window.qsize() >= window_size:
                #        instr_window.get()
                #        #instr_window_sq.get()
                #
                #    instr_window.put(float(total))
                #    #instr_window_sq.put(float(total) * float(total))
                #
                #    # update running mean & stddev
                #    if samplenum >= window_size:
                #        instr_mean = sum(list(instr_window.queue)) / window_size
                #        #instr_stddev = math.sqrt((sum(list(instr_window_sq.queue)) / window_size) - (instr_mean * instr_mean))
                #
                #        #check for possible inflection (change by more than x times mean)
                #        if total >= (instr_mean * req_mean_mult):
                #            possible_starts.append(samplenum)
                #        if total <= (instr_mean / req_mean_mult):
                #            possible_stops.append(samplenum)

    # no duration for first interval so just copy 2nd interval
    sum_dict[0]['duration'] = sum_dict[1]['duration']
    sum_dict[0]['TSC'] = sum_dict[1]['TSC']
    if self.GENERATE_PER_CORE:
        per_core_dict[0]['duration'] = per_core_dict[1]['duration']
        per_core_dict[0]['TSC'] = per_core_dict[1]['TSC']
    
    processing_end_time = time.time()
    #print("%d secs"%(processing_end_time - start_time))

    #print("\tConverting to DataFrame...", end='', flush=True)
    # need to convert to df because not every interval in dict has same columns (keys). df fills in with nan.
    sum_df = pd.DataFrame.from_dict(sum_dict, "index")
    sorted_cols = list(sum_df.columns.values).sort(key=self.alphanum_key)
    sum_df = sum_df.reindex(columns=sorted_cols)
    if self.GENERATE_PER_CORE:
        per_core_df = pd.DataFrame.from_dict(per_core_dict, "index")
        sorted_cols = list(per_core_df.columns.values).sort(key=self.alphanum_key)
        per_core_df = per_core_df.reindex(columns=sorted_cols)
    convert_end_time = time.time()
    #print("%d secs"%(convert_end_time - processing_end_time))

    
    ## find potential workload start point
    #algo_iterations = 3 # run algorithm a few times, widening criteria each time
    ## max interval distance between potential start/stop points to be considered 'in a row' (allows for errant spikes)
    #max_point_gap = 3  # determined by trial & error; not a perfect scheme
    #skip_percent = 10  # skip this % in the beginning to jump ahead of most noise from starting harness/workload
    ## must have this many start/stop points in a row (each <= max_point_gap from eachother)
    ##min_points_in_row = int(1 / sum_df['duration'].mean())  # determined by trial & error; not a perfect scheme
    #min_points_in_row = window_size
    #true_start = entry['start']
    #start_iterations = 1  # fewer iterations of algo means higher confidence
    #if true_start is None:
    #    for i in range(algo_iterations):
    #        #print(max_point_gap, " : ", min_points_in_row)
    #        starts_in_row = 0
    #        beginning_of_row = None
    #        last_start = None
    #        for possible_start in possible_starts:
    #            if possible_start >= int(sum_df['interval'].max() * (skip_percent / 100.0)):
    #                #print(possible_start, " -> ", starts_in_row)
    #                if beginning_of_row is None:
    #                    beginning_of_row = possible_start
    #
    #                if last_start is None or possible_start - last_start <= max_point_gap:  # count as "row" of stops if points are <= y apart
    #                    starts_in_row += 1
    #                else:
    #                    if starts_in_row >= min_points_in_row: # stop when we find first sample with x in a row that are <= y apart
    #                        break
    #                    beginning_of_row = possible_start
    #                    starts_in_row = 1
    #
    #                last_start = possible_start
    #
    #        if starts_in_row >= min_points_in_row: # stop when we find first sample with x in a row that are <= y apart
    #            if beginning_of_row < (len(sum_df.index) - window_size):  # if we're within a window_size of the end of the WL, don't count it
    #                true_start = beginning_of_row
    #                break
    #
    #        max_point_gap = int(max_point_gap * 2)
    #        min_points_in_row = int(min_points_in_row / 2)
    #        start_iterations += 1


    ## find potential workload stop point
    ## max interval distance between potential start/stop points to be considered 'in a row' (allows for errant spikes)
    #max_point_gap = 3  # determined by trial & error; not a perfect scheme
    ## must have this many start/stop points in a row (each <= max_point_gap from eachother)
    ##min_points_in_row = int(5 / sum_df['duration'].mean())  # determined by trial & error; not a perfect scheme
    #min_points_in_row = window_size
    #true_stop = entry['stop']
    #stop_iterations = 1  # fewer iterations of algo means higher confidence
    #if true_stop is None:
    #    for i in range(algo_iterations):
    #        stops_in_row = 0
    #        beginning_of_row = None
    #        last_stop = None
    #       for possible_stop in possible_stops:
    #            if true_start is not None and possible_stop <= (true_start + window_size): # don't pick a stop that is less than or within one window of the start
    #                continue
    #
    #            if beginning_of_row is None:
    #                beginning_of_row = possible_stop
    #
    #            if last_stop is None or possible_stop - last_stop <= max_point_gap:  # count as "row" of stops if points are <= y apart
    #                stops_in_row += 1
    #            else:
    #                if stops_in_row >= min_points_in_row: # stop when we find first sample with x in a row that are <= y apart
    #                    break
    #                beginning_of_row = possible_stop
    #                stops_in_row = 1
    #
    #            last_stop = possible_stop
    #
    #        if stops_in_row >= min_points_in_row: # stop when we find first sample with x in a row that are <= y apart
    #            true_stop = beginning_of_row #+ int(min_points_in_row / 2)
    #            break
    #
    #        max_point_gap = int(max_point_gap * 2)
    #        min_points_in_row = int(min_points_in_row / 2)
    #        stop_iterations += 1

            
    # define a name for the confidence level based on how many iterations it took to find a start/stop
    #confidence_dict = {1: "high", 2: "med", 3: "low"}
    
    #if start_iterations in confidence_dict:
    #    start_confidence = confidence_dict[start_iterations]
    #else:
    #start_confidence = "no"
        
    #if stop_iterations in confidence_dict:
    #    stop_confidence = confidence_dict[stop_iterations]
    #else:
    #stop_confidence = "no"
            
            
    ## if didn't find suggested start/stop, set them to beginning or end of workload
    #if true_start is None:
    #    true_start = 0
    #if true_stop is None:
    #    true_stop = len(sum_df.index) - 1
    
    # naively just cut off first and last x% unless user specifies start/stop interval
    #if true_start is None or true_start == "None" or math.isnan(true_start):
    #    true_start = int(sum_df['interval'].max() * (skip_percent / 100.0))
    #if true_stop is None or true_stop == "None" or math.isnan(true_stop):
    #    true_stop = sum_df['interval'].max() - (int(sum_df['interval'].max() * (skip_percent / 100.0)))
            
    # temporary to cleanup dirs
    #output_bytes = subprocess.check_output("rm -f %s/*.csv"%(emon_dir), shell=True)
  
 
    # add some tags & constants
    sum_df = self.add_entry_info(sum_df, entry)
    
    if self.GENERATE_PER_CORE:
      per_core_df = self.add_entry_info(per_core_df, entry)

    # write to csv
    sum_df.to_csv(outfile, chunksize=1e6)
    if self.GENERATE_PER_CORE:
        if self.INTERMEDIATE == True:
            per_core_file = self.results_dir + "/workloads/" + run + "/" + run + "_emon_per_core.csv"
        else:
            per_core_file = emon_dir + "/" + run + "_emon_per_core.csv"
        per_core_df.to_csv(per_core_file, chunksize=1e6)

    self.logging.log("info", "Converted %s to csv in %d secs"%(run, time.time() - start_time))
    return True
