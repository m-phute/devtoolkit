import os
import pandas as pd
import time
import math
from pandas.api.types import is_numeric_dtype


# most of the avg columns are added metrics just in case
avg_cols = ['metric_Arithmetic Intensity', 'metric_GFLOPS/s', 'metric_FLOPS','metric_FLOPS.256B_PACKED_SINGLE(%)',
            'metric_FLOPS.256B_PACKED_DOUBLE(%)', 'metric_FLOPS.512B_PACKED_SINGLE(%)', 'metric_FLOPS.512B_PACKED_DOUBLE(%)',
            'metric_CPU operating frequency (in GHz)', 'metric_CPU utilization %', 'metric_CPU utilization% in kernel mode',
            'metric_CPI', 'metric_kernel_CPI', 'metric_EMON event mux reliability% (>95% good)',
            'metric_branch mispredict ratio', 'metric_loads per instr', 'metric_stores per instr',
            'metric_locks retired per instr', 'metric_uncacheable reads per instr',
            'metric_streaming stores (full line) per instr', 'metric_streaming stores (partial line) per instr',
            'metric_L1D MPI (includes data+rfo w/ prefetches)', 'metric_L1D demand data read hits per instr',
            'metric_L1-I code read misses (w/ prefetches) per instr', 'metric_L2 demand data read hits per instr',
            'metric_L2 MPI (includes code+data+rfo w/ prefetches)', 'metric_L2 demand data read MPI',
            'metric_L2 demand code MPI', 'metric_L2 Any local request that HITM in a sibling core (per instr)',
            'metric_L2 Any local request that HIT in a sibling core and forwarded(per instr)',
            'metric_L2 % of all lines evicted that are unused prefetches',
            'metric_L2 % of L2 evictions that are allocated into L3',
            'metric_L2 % of L2 evictions that are NOT allocated into L3',
            'metric_LLC code references per instr (L3 prefetch excluded)',
            'metric_LLC data read references per instr (L3 prefetch excluded)',
            'metric_LLC RFO references per instr (L3 prefetch excluded)',
            'metric_LLC MPI (includes code+data+rfo w/ prefetches)', 'metric_LLC data read MPI (demand+prefetch)',
            'metric_LLC RFO read MPI (demand+prefetch)', 'metric_LLC code read MPI (demand+prefetch)',
            'metric_LLC total HITM (per instr) (excludes LLC prefetches)',
            'metric_LLC total HIT clean line forwards (per instr) (excludes LLC prefetches)',
            'metric_Average LLC data read (demand+prefetch) miss latency (in UNCORE clk)',
            'metric_Average LLC data read (demand+prefetch) miss latency  for LOCAL requests (in UNCORE clk)',
            'metric_Average LLC data read (demand+prefetch) miss latency  for REMOTE requests (in UNCORE clk)',
            'metric_LLC Local code/data reads hitting in S state in snoop filter per instr',
            'metric_LLC Local code/data reads hitting in E state in snoop filter per instr',
            'metric_LLC Local code/data reads hitting in S state in LLC per instr',
            'metric_LLC Local code/data reads hitting in M/E/F states in LLC per instr',
            'metric_LLC Remote snoops hitting in S state in snoop filter per instr',
            'metric_LLC Remote snoops hitting in E state in snoop filter per instr',
            'metric_LLC Remote snoops hitting in S state in LLC per instr', 'metric_ITLB MPI',
            'metric_ITLB large page MPI', 'metric_DTLB load MPI', 'metric_DTLB large page load MPI',
            'metric_DTLB store MPI', 'metric_DTLB load miss latency (in core clks)',
            'metric_DTLB store miss latency (in core clks)', 'metric_ITLB miss latency (in core clks)',
            'metric_NUMA %_Reads addressed to local DRAM', 'metric_NUMA %_Reads addressed to remote DRAM',
            'metric_UPI Data transmit BW (MB/sec) (only data)', 'metric_UPI Transmit utilization_% (includes control)',
            'metric_UPI % cycles transmit link is half-width (L0p)', 'metric_UPI % cycles receive link is half-width (L0p)',
            'metric_HA - Reads vs. all requests', 'metric_HA - Writes vs. all requests', 'metric_HA % of all reads that are local',
            'metric_HA % of all writes that are local', 'metric_HA conflict responses per instr',
            'metric_HA directory lookups that spawned a snoop (per instr)',
            'metric_HA directory lookups that did not spawn a snoop (per instr)', 'metric_M2M directory updates (per instr)',
            'metric_M2M extra reads from XPT-UPI prefetches (per instr)', 'metric_memory bandwidth read (MB/sec)',
            'metric_memory bandwidth write (MB/sec)', 'metric_memory bandwidth total (MB/sec)',
            'metric_memory extra read b/w due to XPT prefetches (MB/sec)',
            'metric_memory extra write b/w due to directory updates (MB/sec)',
            'metric_memory average number of entries in each read Q (RPQ)',
            'metric_memory average number of entries in each write Q (WPQ)', 'metric_3DXP_memory bandwidth read (MB/sec)',
            'metric_3DXP_memory bandwidth write (MB/sec)', 'metric_3DXP_memory bandwidth total (MB/sec)',
            'metric_IO_bandwidth_disk_or_network_writes (MB/sec)', 'metric_IO_bandwidth_disk_or_network_reads (MB/sec)',
            'metric_IO_number of partial PCI writes per sec', 'metric_IO_write cache miss(disk/network reads) bandwidth (MB/sec)',
            'metric_IO_read cache miss(disk/network writes) bandwidth (MB/sec)', 'metric_MMIO reads per instr',
            'metric_MMIO writes per instr', 'metric_memory reads vs. all requests', 'metric_memory Page Empty vs. all requests',
            'metric_memory Page Misses vs. all requests', 'metric_memory Page Hits vs. all requests',
            'metric_memory % Cycles where all DRAM ranks are in PPD mode',
            'metric_memory % Cycles all ranks in critical thermal throttle',
            'metric_memory % Cycles Memory is in self refresh power mode',
            'metric_ItoM operations (fast strings) that reference LLC per instr',
            'metric_ItoM operations (fast strings) that miss LLC per instr', 'metric_% Uops delivered from decoded Icache (DSB)',
            'metric_% Uops delivered from legacy decode pipeline (MITE)', 'metric_% Uops delivered from microcode sequencer (MS)',
            'metric_% Uops delivered from loop stream detector (LSD)',
            'metric_FP scalar single-precision FP instructions retired per instr',
            'metric_FP scalar double-precision FP instructions retired per instr',
            'metric_FP 128-bit packed single-precision FP instructions retired per instr',
            'metric_FP 128-bit packed double-precision FP instructions retired per instr',
            'metric_FP 256-bit packed single-precision FP instructions retired per instr',
            'metric_FP 256-bit packed double-precision FP instructions retired per instr',
            'metric_FP 512-bit packed single-precision FP instructions retired per instr',
            'metric_FP 512-bit packed double-precision FP instructions retired per instr', 'metric_DRAM power (watts)',
            'metric_package power (watts)', 'metric_core c3 residency %', 'metric_core c6 residency %', 'metric_package c2 residency %',
            'metric_package c3 residency %', 'metric_package c6 residency %', 'metric_TMAM_Info_CoreIPC',
            'metric_TMAM_Info_Memory Level Parallelism', 'metric_TMAM_Info_cycles_both_threads_active(%)',
            'metric_TMAM_Frontend_Bound(%)', 'metric_TMAM_..Frontend_Latency(%)', 'metric_TMAM_....ICache_Misses(%)',
            'metric_TMAM_....ITLB_Misses(%)', 'metric_TMAM_....Branch_Resteers(%)', 'metric_TMAM_....DSB_Switches(%)',
            'metric_TMAM_....MS_Switches(%)', 'metric_TMAM_..Frontend_Bandwidth(%)', 'metric_TMAM_Bad_Speculation(%)',
            'metric_TMAM_..Branch_Mispredicts(%)', 'metric_TMAM_..Machine_Clears(%)', 'metric_TMAM_Backend_bound(%)',
            'metric_TMAM_..Memory_Bound(%)', 'metric_TMAM_....L1_Bound(%)', 'metric_TMAM_......DTLB_Load(%)',
            'metric_TMAM_......Store_Fwd_Blk(%)', 'metric_TMAM_......Lock_Latency(%)', 'metric_TMAM_....L2_Bound(%)',
            'metric_TMAM_....L3_Bound(%)', 'metric_TMAM_......Contested_Accesses(%)', 'metric_TMAM_......Data_Sharing(%)',
            'metric_TMAM_......L3_Latency(%)', 'metric_TMAM_......L3_Bandwidth(%)', 'metric_TMAM_......SQ_Full(%)',
            'metric_TMAM_....MEM_Bound(%)', 'metric_TMAM_......MEM_Bandwidth(%)', 'metric_TMAM_......MEM_Latency(%)',
            'metric_TMAM_....Stores_Bound(%)', 'metric_TMAM_......DTLB_Store(%)', 'metric_TMAM_..Core_Bound(%)',
            'metric_TMAM_....Divider(%)', 'metric_TMAM_....Ports_Utilization(%)', 'metric_TMAM_......0_Ports_Utilized(%)',
            'metric_TMAM_......1_Port_Utilized(%)', 'metric_TMAM_......2_Ports_Utilized(%)', 'metric_TMAM_......3m_Ports_Utilized(%)',
            'metric_TMAM_Retiring(%)', 'metric_TMAM_..Base(%)', 'metric_TMAM_....FP_Arith(%)', 'metric_TMAM_....Other(%)',
            'metric_TMAM_..Microcode_Sequencer(%)', 'metric_GFLOPS/s.SCALAR_SINGLE', 'metric_GFLOPS/s.SCALAR_DOUBLE',
            'metric_GFLOPS/s.128B_PACKED_DOUBLE', 'metric_GFLOPS/s.128B_PACKED_SINGLE', 'metric_GFLOPS/s.256B_PACKED_SINGLE',
            'metric_GFLOPS/s.256B_PACKED_DOUBLE', 'metric_GFLOPS/s.512B_PACKED_SINGLE', 'metric_GFLOPS/s.512B_PACKED_DOUBLE',
            'metric_FLOPS.SCALAR_SINGLE(%)', 'metric_FLOPS.SCALAR_DOUBLE(%)', 'metric_FLOPS.128B_PACKED_DOUBLE(%)',
            'metric_FLOPS.128B_PACKED_SINGLE(%)']

max_cols = ['timestamp', 'unix_Timestamp', 'system.tsc_freq', 'system.sockets[1][0].size',
            'system.sockets[1].cores.count', 'system.sockets[1].cpus.count', 'system.sockets[0][0].size', 'system.sockets[0].cores.count', 'system.sockets[0].cpus.count',
            'system.sockets.count', 'system.socket_count','system.cha_count/system.socket_count', 'number_of_online_processors', 'suggested_start', 'suggested_stop',
            'interval', 'suggested_start_confidence', 'suggested_stop_confidence', 'raw_emon', 'dram_channels',
            'performance', 'perf', 'run', 'workload', 'instances', 'cores per instance', 'cores used', 'core freq',
            'uncore freq', 'DRAM freq', 'metrics', 'node', 'cpu_family', 'cpu_short', 'namespace', 'agg_secs', 'cum_duration']

# everything else will be 'summed' to new granularity


def aggregate(self, entry):
    run = entry['name']
    new_granularity_sec = entry['agg_secs']
    emon_dir = entry['emon_dir']
    start_time = time.time()

    if self.INTERMEDIATE == True:
        infile = self.results_dir + "/workloads/" + run + "/" + run + "_emon_sum.csv"
        outfile = self.results_dir + "/workloads/" + run + "/%s_emon_%.3fsec.csv"%(run, new_granularity_sec)
    else:
        infile = emon_dir + "/" + run + "_emon_sum.csv"
        outfile = emon_dir + "/%s_emon_%.3fsec.csv"%(run, new_granularity_sec)
    
    if os.path.isfile(outfile):
        if self.OVERWRITE == False:
            return True
        else:
            os.remove(outfile)

    if not os.path.isfile(infile):
        self.logging.log("warning", "Can't find %s to aggregate"%(infile))
        if os.path.isfile(outfile):
            os.remove(outfile)
        return False
    
    self.logging.log("info", "Aggregating %s..."%(run))

    # read in csv, create temp df
    csv = pd.read_csv(infile, index_col=0)
    new_dict = {}
    df_sum = pd.DataFrame(columns=csv.columns)
    df_max = pd.DataFrame(columns=csv.columns)
    df_avg = pd.DataFrame(columns=csv.columns)
    df = pd.DataFrame(columns=csv.columns)

    # check if need to aggregate
    current_granularity_sec = float('%.3f'%(csv['duration'].mean()))
    current_stddev_sec = float('%.3f'%(csv['duration'].std()))
    if current_granularity_sec > new_granularity_sec or new_granularity_sec / current_granularity_sec < 1.1:
        self.logging.log("warning", "%s current granularity %.3f is already greater than or close enough to %.3f"%(run, current_granularity_sec, new_granularity_sec))
        csv.to_csv(outfile)
        return True
    if current_stddev_sec >= (current_granularity_sec / 2.0):
        self.logging.log("error", "%s interval duration %.3f std dev is too large @ %.3f, might be a bad run"%(run, current_granularity_sec, current_stddev_sec))
        if os.path.isfile(outfile):
            os.remove(outfile)
        return False
    
    intervals_to_combine = math.ceil(new_granularity_sec / current_granularity_sec)
    
    if intervals_to_combine > len(csv):
        self.logging.log("error", "%s interval count %d less than required %d"%(run, len(csv), intervals_to_combine))
        if os.path.isfile(outfile):
            os.remove(outfile)
        return False

    # calculate avg, max, sum based on column and aggregate (uses dict instead of df for speed)
    new_interval = 0
    for i in range(0, len(csv.index), intervals_to_combine):
        new_dict[new_interval] = {}
        for label in list(csv):
            if label in max_cols:
                new_dict[new_interval][label] = csv.iloc[i:i+intervals_to_combine][label].max()
            elif label in avg_cols:
                new_dict[new_interval][label] = csv.iloc[i:i+intervals_to_combine][label].mean()
            else:
                if is_numeric_dtype(csv[label]):  # sum
                    new_dict[new_interval][label] = csv.iloc[i:i+intervals_to_combine][label].mean() * (new_granularity_sec / current_granularity_sec)
                else:  # max
                    new_dict[new_interval][label] = csv.iloc[i:i+intervals_to_combine][label].max()
        new_interval += 1
    df = pd.DataFrame.from_dict(new_dict, "index")
            
    # reset interval numbers
    df['interval'] = df.index
    
    # fix suggested start & stop intervals due to aggregation
    #df['suggested_start'] = df['suggested_start'].map(lambda x: math.floor(x / intervals_to_combine) if x is not None and x != "None" else x)
    #df['suggested_stop'] = df['suggested_stop'].map(lambda x: math.floor(x / intervals_to_combine) if x is not None and x != "None" else x)
        
    #print(df)
    df.to_csv(outfile)

    self.logging.log("info", "Aggregated %s in %d secs, combining %d intervals for %.3f -> %.3f sec"%(
        run, time.time() - start_time, intervals_to_combine, current_granularity_sec, new_granularity_sec))
    return True
