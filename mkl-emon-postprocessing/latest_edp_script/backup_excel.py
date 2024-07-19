import copy
import subprocess
import sys
import os
import math
import log
import time
import xlsxwriter
import pandas as pd
from xlsxwriter.utility import xl_rowcol_to_cell
from datetime import datetime


bb_columns = [
    'metric_CPI', 'metric_L1D demand data read hits per instr', 'metric_L2 demand data read hits per instr',
    'metric_L2 demand data read MPI', 'metric_ITLB MPI', 'metric_DTLB load MPI', 'metric_DTLB store MPI',
    'DIVIDERPI', 'BACPI', 'ABRPI', 'JECPI',
    'metric_LLC MPI (includes code+data+rfo w/ prefetches)',
    'metric_Average LLC data read (demand+prefetch) miss latency (in ns)',
    'metric_CPU operating frequency (in GHz)',
]
proxy_columns = [
    'metric_CPI', 'metric_NUMA %_Reads addressed to local DRAM', 'L3 MPKI', 'L2 MPKI', 'DDR BW/core (GB/s)', 
    'metric_Average LLC data read (demand+prefetch) miss latency (in ns)', 'Remote hitm (%LLC miss)', 'metric_LLC % misses',
    'DDR Rd Ratio', 'metric_IO_bandwidth_disk_or_network_total (MB/sec)', 'CPU Utilization used threads %',
    'metric_UPI Transmit utilization_% (includes control)', 'metric_memory bandwidth utilization %',
    'metric_TMAM_Frontend_Bound(%)', 'metric_TMAM_Backend_bound(%)', 'metric_TMAM_Bad_Speculation(%)',
    'metric_TMAM_Retiring(%)', 'metric_Arithmetic Intensity', 'FP Utilization %', 'FP Efficiency %',
]
proxy_rename = [
    'CPI', 'NUMA %local', 'L3 MPKI', 'L2 MPKI', 'DRAM GB/s per core', 'DRAM Lat ns', 'Remote hitm of %LLC miss',
    'LLC Miss Rate', 'DDR Rd/Wr', 'IO MB/s', 'CPU Util', 'UPI Util', 'DRAM BW Util', 'Frontend Bound',
    'Backend Bound', 'Bad Spec', 'Retiring', 'Intensity', 'FP Util', 'FP Eff',
]

def create_excel(self, entry):
    run = entry['name']
    emon_dir = entry['emon_dir']
    metrics = entry['metrics']
    new_granularity_sec = entry['agg_secs']
    start_time = time.time()
   
    if self.INTERMEDIATE == True:
        infile = self.results_dir + "/workloads/" + run + "/%s_emon_%.3fsec_metrics.csv"%(run, new_granularity_sec)
        outfile = self.results_dir + "/workloads/" + run + "/%s_emon_%.3fsec_metrics.xlsx"%(run, new_granularity_sec)
    else:
        infile = emon_dir + "/%s_emon_%.3fsec_metrics.csv"%(run, new_granularity_sec)
        outfile = emon_dir + "/%s_emon_%.3fsec_metrics.xlsx"%(run, new_granularity_sec)
 
    if os.path.isfile(outfile):
        if self.OVERWRITE == False:
            return True
        else:
            os.remove(outfile)
    
    if not os.path.isfile(infile):
        self.logging.log("warning", "Can't find %s to create excel"%(infile))
        if os.path.isfile(outfile):
            os.remove(outfile)
        return False

    self.logging.log("info", "Creating Excel for %s..."%(run))
    
    #read in input csv
    df = pd.read_csv(infile, index_col=0)
    first_row = 1
    last_row = len(df.index)
    start_row = df['suggested_start'].values[0] + first_row
    end_row = df['suggested_stop'].values[0] + first_row
    
    #create xlsx writer and save EMON data
    writer = pd.ExcelWriter(outfile, engine='xlsxwriter')
    df.to_excel(writer, sheet_name='EMON')
    workbook = writer.book
    
    #create bounding box summary tab
    if set(bb_columns).issubset(df.columns):
        bb_df = df.loc[df['suggested_start'].values[0]:df['suggested_stop'].values[0]][bb_columns].mean()
        bb_df = bb_df.transpose()
        bb_df.to_excel(writer, sheet_name='Bounding Box')

    # create proxy metrics summary tab
    if not set(proxy_columns).issubset(df.columns):
        for column in proxy_columns:
            if column not in df:
                df[column] = None
    proxy_df = df.loc[df['suggested_start'].values[0]:df['suggested_stop'].values[0]][proxy_columns]
    proxy_df.columns = proxy_rename
    proxy_df = proxy_df.mean()
    proxy_df = proxy_df.transpose()
    proxy_df.to_excel(writer, sheet_name='Proxy Metrics')
    
    # create general chart(s)
    workbook.add_worksheet('Charts')
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='scatter',
        chart_subtype='smooth',
        start_row=first_row,
        end_row=last_row,
        x_col_names='cum_duration',
        y_col_names=['INST_RETIRED.ANY'],
        series_names=['Instructions Retired'],
        title='Instructions Retired & Suggested Filter',
        x_label='Time (s)',
        y_label='Instructions Retired',
        y_min=0,
        additional_series=[
            {
                'name':       'Start',
                'categories': [df.loc[df['suggested_start'].values[0]]['cum_duration'], df.loc[df['suggested_start'].values[0]]['cum_duration']],
                'values':     [0, df['INST_RETIRED.ANY'].max()],
                'line':       {'color': 'green'},
                'marker':     {'type': 'none'},
            },
            {
                'name':       'Stop',
                'categories': [df.loc[df['suggested_stop'].values[0]]['cum_duration'], df.loc[df['suggested_stop'].values[0]]['cum_duration']],
                'values':     [0, df['INST_RETIRED.ANY'].max()],
                'line':       {'color': 'red'},
                'marker':     {'type': 'none'},
            },
        ]
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='scatter',
        chart_subtype='smooth',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=['metric_CPU utilization %','CPU Utilization used threads %'],
        series_names=['CPU utilization % all threads','CPU Utilization % used threads'],
        title='CPU Utilization over Time',
        x_label='Time (s)',
        y_label='CPU Util (%)',
        y_min=0,
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='scatter',
        chart_subtype='smooth',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=['metric_memory bandwidth utilization %'],
        series_names=['DRAM BW Utilization %'],
        title='DRAM BW Utilization over Time',
        x_label='Time (s)',
        y_label='DRAM BW Util (%)',
        disable_legend=True,
        y_min=0,
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='area',
        chart_subtype='stacked',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=['aibt_max_active_mem', 'aibt_max_cached_mem', 'aibt_min_available_mem'],
        series_names=['Active', 'Cached', 'Available'],
        title='DRAM Footprint over Time',
        x_label='Time (s)',
        y_label='GB',
        disable_legend=False,
        y_min=0,
        num_format='0',
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='scatter',
        chart_subtype='smooth',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=['metric_Average LLC data read (demand+prefetch) miss latency (in ns)'],
        series_names=['DRAM Read Latency'],
        title='DRAM Latency over Time',
        x_label='Time (s)',
        y_label='DRAM Read Latency (ns)',
        disable_legend=True,
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='scatter',
        chart_subtype='smooth',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=['DDR Rd Ratio'],
        title='DRAM RD/WR Ratio over Time',
        x_label='Time (s)',
        y_label='DRAM RD/WR',
        disable_legend=True,
        y_min=0,
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='scatter',
        chart_subtype='smooth',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=['metric_CPI'],
        series_names=['CPI'],
        title='CPI over Time',
        x_label='Time (s)',
        y_label='CPI',
        disable_legend=True,
        y_min=0,
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='scatter',
        chart_subtype='smooth',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=['L3 MPKI', 'L2 MPKI'],
        title='MPKI over Time',
        x_label='Time (s)',
        y_label='MPKI',
        y_min=0,
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='scatter',
        chart_subtype='smooth',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=[
            'metric_IO_bandwidth_disk_or_network_writes (MB/sec)',
            'metric_IO_bandwidth_disk_or_network_reads (MB/sec)',
        ],
        series_names=['IO BW disk or network Writes','IO BW disk or network Reads'],
        title='IO Bandwidth over Time',
        x_label='Time (s)',
        y_label='IO BW (MB/s)',
        y_min=0,
    )
    if 'metric_Arithmetic Intensity' in df and 'Roofline Elbow' in df and 'Theoretical Peak GFLOPS/s' in df and 'metric_GFLOPS/s' in df:
        self.add_chart(
            workbook=workbook,
            chartsheet='Charts',
            datasheet='EMON',
            df=df,
            chart_type='scatter',
            start_row=start_row,
            end_row=end_row,
            x_col_names='metric_Arithmetic Intensity',
            y_col_names=['metric_GFLOPS/s'],
            series_names=['GFLOPS/s'],
            title='Roofline',
            x_label='Arithmetic Intensity',
            y_label='GFLOPS/s',
            disable_legend=True,
            x_log_base=10,
            y_log_base=10,
            x_min=1e-6,
            x_max=1e3,
            y_min=1e-6,
            additional_series=[
                {
                    'name':       'Roofline',
                    'categories': [1e-100, df['Roofline Elbow'].max(), 1e3],
                    'values':     [1e-100, df['Theoretical Peak GFLOPS/s'].max(), df['Theoretical Peak GFLOPS/s'].max()],
                    'line':       {'color': 'black'},
                    'marker':     {'type': 'none'},
                },
                {
                    'name':       'Average',
                    'categories': [df.loc[df['suggested_start'].values[0]:df['suggested_stop'].values[0]]['metric_Arithmetic Intensity'].mean()],
                    'values':     [df.loc[df['suggested_start'].values[0]:df['suggested_stop'].values[0]]['metric_GFLOPS/s'].mean()],
                    'marker':     {'type': 'circle', 'fill': {'color': 'red'}, 'border': {'color': 'red'}}
                },
            ]
        )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='scatter',
        chart_subtype='smooth',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=['metric_GFLOPS/s'],
        title='GFLOPS/s',
        x_label='Time (s)',
        y_label='GFLOPS/s',
        y_min=0,
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='scatter',
        chart_subtype='smooth',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=['FP Utilization %', 'FP Efficiency %'],
        title='Floating Point Usage',
        x_label='Time (s)',
        y_label='FP (%)',
        y_min=0,
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='area',
        chart_subtype='stacked',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=[
            'metric_FLOPS.SCALAR_SINGLE(%)',
            'metric_FLOPS.SCALAR_DOUBLE(%)',
            'metric_FLOPS.128B_PACKED_SINGLE(%)',
            'metric_FLOPS.128B_PACKED_DOUBLE(%)',
            'metric_FLOPS.256B_PACKED_SINGLE(%)',
            'metric_FLOPS.256B_PACKED_DOUBLE(%)',
            'metric_FLOPS.512B_PACKED_SINGLE(%)',
            'metric_FLOPS.512B_PACKED_DOUBLE(%)',
        ],
        series_names=[
            'Scalar Single',
            'Scalar Double',
            '128B Packed Single',
            '128B Packed Double',
            '256B Packed Single',
            '256B Packed Double',
            '512B Packed Single',
            '512B Packed Double',
        ],
        title='Floating Point Breakdown',
        x_label='Time (s)',
        y_label='% FP Mix',
        y_min=0,
        y_max=100,
        num_format='0',
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='area',
        chart_subtype='stacked',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=[
            'metric_TMAM_Retiring(%)',
            'metric_TMAM_Frontend_Bound(%)',
            'metric_TMAM_Backend_bound(%)',
            'metric_TMAM_Bad_Speculation(%)',
        ],
        series_names=[
            'Retiring',
            'Frontend Bound',
            'Backend Bound',
            'Bad Speculation',
        ],
        title='TMAM Level 1',
        x_label='Time (s)',
        y_label='% Cycles Spent',
        y_min=0,
        y_max=100,
        num_format='0',
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='area',
        chart_subtype='stacked',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=[
            'metric_TMAM_..Base(%)',
            'metric_TMAM_..Microcode_Sequencer(%)',
            'metric_TMAM_..Branch_Mispredicts(%)',
            'metric_TMAM_..Machine_Clears(%)',
            'metric_TMAM_..Frontend_Latency(%)',
            'metric_TMAM_..Frontend_Bandwidth(%)',
            'metric_TMAM_..Core_Bound(%)',
            'metric_TMAM_..Memory_Bound(%)',
        ],
        series_names=[
            'Retiring:Base', 'Retiring:MS-ROM', 'Bad Spec:Branch Mispredict', 'Bad Spec:Machine Clears',
            'Frontend:Latency', 'Frontend:Bandwidth', 'Backend:Core','Backend:Memory'],
        title='TMAM Level 2',
        x_label='Time (s)',
        y_label='% Cycles Spent',
        y_min=0,
        y_max=100,
        num_format='0',
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='area',
        chart_subtype='stacked',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=[
            'metric_TMAM_....FP_Arith(%)',
            'metric_TMAM_....Other(%)',
        ],
        series_names=['Retiring:Base:FP-Arith', 'Retiring:Base:Other'],
        title='TMAM Level 3 Retiring:Base',
        x_label='Time (s)',
        y_label='% Cycles Spent',
        num_format='0',
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='area',
        chart_subtype='stacked',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=[
            'metric_TMAM_....ITLB_Misses(%)',
            'metric_TMAM_....ICache_Misses(%)',
            'metric_TMAM_....Branch_Resteers(%)',
            'metric_TMAM_....DSB_Switches(%)',
            'metric_TMAM_....MS_Switches(%)',
        ],
        series_names=['Frontend:Latency:ITLB Misses', 'Frontend:Latency:ICache Misses',
                      'Frontend:Latency:Branch Resteers', 'Frontend:Latency:DSB Switches',
                      'Frontend:Latency:MS Switches',
        ],
        title='TMAM Level 3 Frontend:Latency',
        x_label='Time (s)',
        y_label='% Cycles Spent',
        num_format='0',
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='area',
        chart_subtype='stacked',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=[
            'metric_TMAM_....Divider(%)',
            'metric_TMAM_....Ports_Utilization(%)',
        ],
        series_names=['Backend:Core:Divider', 'Backend:Core:Port Utilization'],
        title='TMAM Level 3 Backend:Core',
        x_label='Time (s)',
        y_label='% Cycles Spent',
        num_format='0',
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='area',
        chart_subtype='stacked',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=[
            'metric_TMAM_....L1_Bound(%)',
            'metric_TMAM_....L2_Bound(%)',
            'metric_TMAM_....L3_Bound(%)',
            'metric_TMAM_....MEM_Bound(%)',
            'metric_TMAM_....Stores_Bound(%)', 
        ],
        series_names=['Backend:Memory:L1', 'Backend:Memory:L2', 'Backend:Memory:L3',
                      'Backend:Memory:Mem', 'Backend:Memory:Stores'],
        title='TMAM Level 3 Backend:Memory',
        x_label='Time (s)',
        y_label='% Cycles Spent',
        num_format='0',
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='area',
        chart_subtype='stacked',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=[
            'metric_TMAM_......Mispredicts_Resteers(%)',
            'metric_TMAM_......Clears_Resteers(%)',
            'metric_TMAM_......Unknown_Branches_Resteers(%)',
        ],
        series_names=['Frontend:Latency:Branch Resteers:Mispredicts', 'Frontend:Latency:Branch Resteers:Clears',
                      'Frontend:Latency:Branch Resteers:Unknown'],
        title='TMAM Level 4 Frontend:Latency:Branch Resteers',
        x_label='Time (s)',
        y_label='% Cycles Spent',
        num_format='0',
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='area',
        chart_subtype='stacked',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=[
            'metric_TMAM_......DTLB_Load(%)',
            'metric_TMAM_......Store_Fwd_Blk(%)',
            'metric_TMAM_......Lock_Latency(%)',
        ],
        series_names=['Backend:Memory:L1:DTLB Load', 'Backend:Memory:L1:Store Fwd Blk',
                      'Backend:Memory:L1:Lock Latency'],
        title='TMAM Level 4 Backend:Memory:L1',
        x_label='Time (s)',
        y_label='% Cycles Spent',
        num_format='0',
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='area',
        chart_subtype='stacked',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=[
            'metric_TMAM_......Contested_Accesses(%)',
            'metric_TMAM_......Data_Sharing(%)',
            'metric_TMAM_......L3_Latency(%)',
            'metric_TMAM_......L3_Bandwidth(%)',
            'metric_TMAM_......SQ_Full(%)',
        ],
        series_names=['Backend:Memory:L3:Contested Accesses', 'Backend:Memory:L3:Data Sharing',
                      'Backend:Memory:L3:Latency', 'Backend:Memory:L3:Bandwidth', 'Backend:Memory:L3:SQ Full'],
        title='TMAM Level 4 Backend:Memory:L3',
        x_label='Time (s)',
        y_label='% Cycles Spent',
        num_format='0',
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='area',
        chart_subtype='stacked',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=[
            'metric_TMAM_......MEM_Bandwidth(%)',
            'metric_TMAM_......MEM_Latency(%)',
        ],
        series_names=['Backend:Memory:Mem:Bandwidth', 'Backend:Memory:Mem:Latency'],
        title='TMAM Level 4 Backend:Memory:Mem',
        x_label='Time (s)',
        y_label='% Cycles Spent',
        num_format='0',
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='area',
        chart_subtype='stacked',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=[
            'metric_TMAM_......DTLB_Store(%)',
        ],
        series_names=['Backend:Memory:Stores:DTLB'],
        title='TMAM Level 4 Backend:Memory:Stores',
        x_label='Time (s)',
        y_label='% Cycles Spent',
        num_format='0',
    )
    self.add_chart(
        workbook=workbook,
        chartsheet='Charts',
        datasheet='EMON',
        df=df,
        chart_type='area',
        chart_subtype='stacked',
        start_row=start_row,
        end_row=end_row,
        x_col_names='cum_duration',
        y_col_names=[
            'metric_TMAM_......0_Ports_Utilized(%)',
            'metric_TMAM_......1_Ports_Utilized(%)',
            'metric_TMAM_......2_Ports_Utilized(%)',
            'metric_TMAM_......3m_Ports_Utilized(%)',
        ],
        series_names=['Backend:Core:Port Utilization:0', 'Backend:Core:Port Utilization:1',
                      'Backend:Core:Port Utilization:2', 'Backend:Core:Port Utilization:3+'],
        title='TMAM Level 4 Backend:Core:Port Utilization',
        x_label='Time (s)',
        y_label='% Cycles Spent',
        num_format='0',
    )
    
    
    writer.save()
    
    self.logging.log("info", "Created Excel for %s in %d secs"%(run, time.time() - start_time))
    return True




# 'cursor' state for where to position chart in worksheet
chart_position_state = {}

def format_core_freq(self, core_freq):
    try:
        return "{0:.1f}".format(round(core_freq,1))
    except Exception:
        return core_freq


def add_chart(self, workbook, chartsheet, datasheet, df, chart_type, start_row, end_row, y_col_names, title,
              x_col_names=None, chart_subtype=None, x_label=None, y_label=None, x_log_base=None, y_log_base=None,
              x_min=None, x_max=None, y_min=None, y_max=None, disable_legend=False, additional_series=None,
              num_format='General', series_names=None, gap=None, x_interval_unit=None, y_interval_unit=None,
              x_interval_tick=None, y_interval_tick=None, series_filters=None, trendline=None,
              x_visible=True, y_visible=True, x_scale=2, y_scale=2, chart_position='below'):
    
    if workbook not in chart_position_state:
        chart_position_state[workbook] = {}
    if chartsheet not in chart_position_state[workbook]:
        chart_position_state[workbook][chartsheet] = {
            'chart_col' : 1,
            'chart_row_right' : 1,
            'chart_row_below' : 1,
        }

    # reset column position in case we have to write additional series data, it will be hidden behind chart
    if chart_position == 'below':
        chart_col = chart_position_state[workbook][chartsheet]['chart_col'] = 1  # reset column
        chart_row = chart_position_state[workbook][chartsheet]['chart_row_below']
    else:
        chart_col = chart_position_state[workbook][chartsheet]['chart_col']
        chart_row = chart_position_state[workbook][chartsheet]['chart_row_right']

    # check columns exist
    columns = df.columns
    if x_col_names is not None:
        if isinstance(x_col_names, list):
            if not isinstance(x_col_names[0], tuple):
                return False
        else:
            if not x_col_names in columns:
                #print("x-axis %s is not in columns: %s"%(x_col_names, columns))
                return False

    if not isinstance(y_col_names, list):
        y_col_names = [y_col_names]
    for y_col_name in y_col_names: 
        if not y_col_name in columns:
            #print("y-axis %s is not in columns: %s"%(y_col_name, columns))
            return False
    
    # create chart
    chart_worksheet = workbook.get_worksheet_by_name(chartsheet)
    chart = workbook.add_chart({'type': chart_type, 'subtype': chart_subtype})
    chart.show_blanks_as('span')


    # get x_col & categories
    if x_col_names is not None:
        if not isinstance(x_col_names, list):  # if user provided a column name, get the column in the datasheet
            x_col = columns.get_loc(x_col_names) + 1
            categories = [datasheet, start_row, x_col, end_row, x_col]
        else:  # if we got a list for x_col_names then need to save them to new table and build range (':')
            cat_count = 0
            x_col = None
            categories = '=(' 
            for x1,x2 in x_col_names:    
                cat_start_cell = xl_rowcol_to_cell(chart_row + cat_count, chart_col)
                cat_end_cell = xl_rowcol_to_cell(chart_row + cat_count, chart_col + 1)
                chart_worksheet.write_row(cat_start_cell, (x1, x2))
                categories += chartsheet + '!' + cat_start_cell + ':' + cat_end_cell + ','
                cat_count += 1
            categories = categories.rstrip(',') + ')'
    else:
        x_col = None
        categories = None


    # add main series
    for series_idx, y_col_name in enumerate(y_col_names):
        y_col = columns.get_loc(y_col_name) + 1
        if series_names is not None:
            series_name = series_names[series_idx]
        else:
            series_name = y_col_name
        
        if series_filters is None:
            chart.add_series({
                'name':       series_name,
                'categories': categories,
                'values':     [datasheet, start_row, y_col, end_row, y_col],
                'gap':        gap,
                'trendline':  trendline,
            })
        else:
            #find unique combinations, get row/col of each
            filtered_df = self.filter_df(series_filters, df)
           
            if x_col is not None:
                categories = '=('
                for row in filtered_df['row'].values:
                    categories += datasheet + '!' + str(xl_rowcol_to_cell(row+1, x_col)) + ','
                categories = categories.rstrip(',') + ')'
 
            values = '=('
            for row in filtered_df['row'].values:
                values += datasheet + '!' + str(xl_rowcol_to_cell(row+1, y_col)) + ','
            values = values.rstrip(',') + ')'
            
            chart.add_series({
                'name':       series_name,
                'categories': categories,
                'values':     values,
                'gap':        gap,
                'trendline':  trendline,
            })
   
 
    # add additional series formatted by user
    # Could just chart raw values but xlsxwriter prints annoying warning so instead I'll write data to sheet and chart that
    if additional_series is not None:
        cat_count = val_count = 0
        for series in additional_series:
            cat_start_cell = xl_rowcol_to_cell(chart_row + cat_count, chart_col)
            val_start_cell = xl_rowcol_to_cell(chart_row + val_count, chart_col + 2)
            cat_count += len(series['categories'])
            val_count += len(series['values'])
            cat_end_cell = xl_rowcol_to_cell(chart_row + cat_count - 1, chart_col)
            val_end_cell = xl_rowcol_to_cell(chart_row + val_count - 1, chart_col + 2)
            chart_worksheet.write_column(val_start_cell, series['values'])
            series['values'] = chartsheet + '!' + val_start_cell + ':' + val_end_cell

            if series['categories'] == x_col_names:  # if we're using the same tuple of x_cols  
                series['categories'] = categories
            else:
                chart_worksheet.write_column(cat_start_cell, series['categories'])
                series['categories'] = chartsheet + '!' + cat_start_cell + ':' + cat_end_cell

            if 'y2_axis' in series and series['y2_axis'] == True:
                chart2 = workbook.add_chart({'type': series['type'] if 'type' in series else 'line', 'subtype': series['subtype'] if 'subtype' in series else None})
                chart2.show_blanks_as('span')
                chart2.add_series(series)
                chart.combine(chart2)
                chart2.set_y2_axis({
                    'name': series['y2_label'] if 'y2_label' in series else None,
                    'name_font': {'size': 12},
                    'num_font': {'size': 11},
                    'label_position': series['y2_label_position'] if 'y2_label_position' in series else None,
                    'min': series['y2_min'] if 'y2_min' in series else None,
                    'max': series['y2_max'] if 'y2_max' in series else None,
                    'log_base': series['y2_log_base'] if 'y2_log_base' in series else None,
                    'num_format': series['y2_num_format'] if 'y2_num_format' in series else 'General',
                    'interval_unit': series['y2_interval_unit'] if 'y2_interval_unit' in series else None,
                    'interval_tick': series['y2_interval_tick'] if 'y2_interval_tick' in series else None,
                    'visible': series['y2_visible'] if 'y2_visible' in series else True,
                })
            else:
                chart.add_series(series)
        
    # title
    chart.set_title({
        'name': title,
        'name_font': {'size': 18},
    })
    
    # legend
    chart.set_legend({
        'font': {'size': 12},
        'position': 'top',
        'none': disable_legend,
    })
    
    # axis
    chart.set_x_axis({
        'name': x_label,
        'name_font': {'size': 12},
        'num_font': {'size': 11},
        'label_position': 'low',
        'min': x_min,
        'max': x_max,
        'log_base': x_log_base,
        'num_format': num_format,
        'interval_unit': x_interval_unit,
        'interval_tick': x_interval_tick,
        'visible': x_visible,
    })
    chart.set_y_axis({
        'name': y_label,
        'name_font': {'size': 12},
        'num_font': {'size': 11},
        'label_position': 'low',
        'min': y_min,
        'max': y_max,
        'log_base': y_log_base,
        'num_format': num_format,
        'interval_unit': y_interval_unit,
        'interval_tick': y_interval_tick,
        'visible': y_visible,
    })
   
 
    chart_worksheet.insert_chart(chart_row, chart_col, chart, {'x_scale': x_scale, 'y_scale': y_scale})
    chart_position_state[workbook][chartsheet]['chart_col'] = chart_col + (8 * x_scale)  # advance column
    chart_position_state[workbook][chartsheet]['chart_row_right'] = chart_row  # save row in case next chart is 'right'
    chart_position_state[workbook][chartsheet]['chart_row_below'] = chart_row + (15 * y_scale)  # advance row in case next chart is 'below'

    return True


# # # Combine and Summarize

# In[14]:


projection_baseline = {  # measured config
    'skx': {'precision': 32},
    'bdx': {'precision': 32},
    'clx': {'precision': 32},
    'amd': {'precision': 0},
}
projection_targets = [  # projected configs
    {'name': 'skx8180 fp32',   'peak gops': 8960,   'peak gbps': 256,  'precision': 32},
    {'name': 'cpx bfloat16',   'peak gops': 50300,  'peak gbps': 614,  'precision': 16},
    {'name': 'cpx int8',       'peak gops': 50300,  'peak gbps': 614,  'precision': 8},
    {'name': 'cpx int4',       'peak gops': 50300,  'peak gbps': 614,  'precision': 4},
    {'name': 'spr-sp int8',    'peak gops': 313098, 'peak gbps': 614,  'precision': 8},
    {'name': 'spr-sp int4',    'peak gops': 313098, 'peak gbps': 614,  'precision': 4},
    {'name': 'spr-ap int8',    'peak gops': 626196, 'peak gbps': 1229, 'precision': 8},
    {'name': 'spr-ap int4',    'peak gops': 626196, 'peak gbps': 1229, 'precision': 4},
]
projection_comparisons = [  # targets to project to
    {'base': 'skx8180 fp32',  'target': 'cpx bfloat16'},
    {'base': 'skx8180 fp32',  'target': 'cpx int8'},
    {'base': 'skx8180 fp32',  'target': 'cpx int4'},
    {'base': 'skx8180 fp32',  'target': 'spr-sp int8'},
    {'base': 'skx8180 fp32',  'target': 'spr-sp int4'},
    {'base': 'skx8180 fp32',  'target': 'spr-ap int8'},
    {'base': 'skx8180 fp32',  'target': 'spr-ap int4'},
    {'base': 'cpx int8',      'target': 'spr-ap int4'},
    {'base': 'spr-sp int8',   'target': 'spr-ap int4'},
]
projection_charts = [  # what to chart across workloads
    {'base': 'skx8180 fp32',  'target': 'cpx int8'},
    {'base': 'skx8180 fp32',  'target': 'spr-sp int8'},
    {'base': 'skx8180 fp32',  'target': 'spr-ap int4'},
    {'base': 'cpx int8',      'target': 'spr-ap int4'},
    {'base': 'spr-sp int8',   'target': 'spr-ap int4'},
]


def get_baseline_precision(self, row):
    if row['baseline'] in projection_baseline:
        return projection_baseline[row['baseline']]['precision']
    else:
        self.logging.log("warning", "Can't find baseline precision for %s cpu %s!"%(row['run'], row['cpu_short']))
        return 0

    
def try_avg(self, x):
    try: 
        return pd.to_numeric(x).mean()
    except:  # else it's a string or object so just take one value
        return x.dropna().max()

    
def filter_df(self, filters, df):
    filter_string = ""
    for column, values in filters.items():
        if column not in df.columns:
            return None
        else:
            if values is None:  # get all of them
                filter_vals = list(df[column].unique())
            elif type(values) is list:  # get list
                filter_vals = values
            else:  # get one value
                filter_vals = [values]

            #coerce column to string for isin() to work
            if column == 'core freq':
                column = 'string core freq'

            if filter_string != "":
                filter_string += " & "
            filter_string += "(df['" + str(column) + "'].isin(" + str(filter_vals) + "))"

    filter_string = "df.loc[" + filter_string + "]"
    return eval(filter_string)


def calc_scaling(self, workload_df, row, scaling_column):
    if scaling_column not in workload_df.columns:
        self.logging.log("warning", "%s column not in df"%(scaling_column))
        return None
    
    scaling_vals = list(workload_df[scaling_column].unique())
    if 'default' in scaling_vals:
        scaling_vals.remove('default')
    scaling_vals.sort()
    
    # compare against other scaling vals as baseline
    # return None for lowest val so it's not included in avg scaling because it would be 100%
    scaling_ratio = None
    for scaling_val in scaling_vals:
        baseline = workload_df[workload_df[scaling_column] == scaling_val]['performance'][0]
        if baseline is None or math.isnan(baseline) or         row[scaling_column] == 'default' or row[scaling_column] <= scaling_val:
            continue
        
        measured_ratio = float(row['performance']) / float(baseline)
        #if scaling_column == 'string core freq':
        #    ideal_ratio = float(row['metric_CPU operating frequency (in GHz)']) / float(scaling_val)
        #else:
        ideal_ratio = float(row[scaling_column]) / float(scaling_val)
        
        if scaling_ratio is None:
            scaling_ratio = (measured_ratio - 1) / (ideal_ratio - 1)
        else:  # average
            scaling_ratio = (scaling_ratio + ((measured_ratio - 1) / (ideal_ratio - 1))) / 2.0
    
    return scaling_ratio


def calc_pct_change_per_val(self, workload_df, row, scaling_column, value_column):
    if scaling_column not in workload_df.columns or value_column not in workload_df.columns:
        self.logging.log("warning", "%s or %s column not in df"%(scaling_column, value_column))
        return None
    
    scaling_vals = list(workload_df[scaling_column].unique())
    if 'default' in scaling_vals:
        scaling_vals.remove('default')
    scaling_vals.sort()
    
    # compare against other scaling vals as baseline
    # return None for lowest val so it's not included in avg scaling because it would be 100%
    avg_pct_change_per_val = None
    for scaling_val in scaling_vals:
        baseline_perf = workload_df[workload_df[scaling_column] == scaling_val]['performance'][0]
        baseline_val = workload_df[workload_df[scaling_column] == scaling_val][value_column][0]
        if baseline_perf is None or math.isnan(baseline_perf) or baseline_val is None or math.isnan(baseline_val) or        row[scaling_column] == 'default' or row[scaling_column] <= scaling_val:
            continue
        
        pct_change = (float(row['performance']) - float(baseline_perf)) / float(baseline_perf)
        val_diff = (float(baseline_val) - float(row[value_column]))
        pct_change_per_val = pct_change / val_diff
        
        if avg_pct_change_per_val is None:
            avg_pct_change_per_val = pct_change_per_val
        else:  # average
            avg_pct_change_per_val = (avg_pct_change_per_val + pct_change_per_val) / 2.0
        
    if avg_pct_change_per_val is not None:
        avg_pct_change_per_val *= 100
        
    return avg_pct_change_per_val


def create_filter_summary(self, workloads):
    self.logging.log('info', "Creating Filter Summary...")
    main_columns = ['run', 'interval', 'INST_RETIRED.ANY', 'suggested_start', 'suggested_stop']
    added_columns = []
    filter_summary = pd.DataFrame()
    filter_summary_file = self.results_dir + "/filter_summary.xlsx" 
    for entry in workloads:
        desired_columns = copy.deepcopy(main_columns)
        run = entry['name']
        emon_dir = entry['emon_dir']
        metrics = entry['metrics']
        new_granularity_sec = entry['agg_secs']
       
        if self.INTERMEDIATE == True:
            infile = self.results_dir + "/workloads/" + run + "/%s_emon_%.3fsec_metrics.csv"%(run, new_granularity_sec)
        else:
            infile = emon_dir + "/%s_emon_%.3fsec_metrics.csv"%(run, new_granularity_sec)
 
        if os.path.isfile(infile):
            whole_workload = pd.read_csv(infile, index_col=0)
            if len(whole_workload) <= 1:
                self.logging.log("info", "ignoring %s because it only has %d rows"%(run, len(whole_workload)))
            else:
                self.logging.log("info", "%s has %d rows: %s"%(run, len(whole_workload), infile)) if self.VERBOSE == True else 0
                if 'filter_column' in list(whole_workload) and pd.isnull(whole_workload['filter_column'][0]) == False and whole_workload['filter_column'][0] in list(whole_workload) and whole_workload['filter_column'][0] not in main_columns:
                  desired_columns.append(whole_workload['filter_column'][0])
                  if whole_workload['filter_column'][0] not in added_columns and whole_workload['filter_column'][0] not in main_columns:
                    added_columns.append(whole_workload['filter_column'][0])
                filter_summary = filter_summary.append(whole_workload[desired_columns] , ignore_index=True, sort=False)
        else:
            self.logging.log("warning", "Can't find %s to create filter summary"%(infile))
           
    filter_summary = filter_summary.sort_values(['run', 'interval']).reset_index(drop=True)  # sort by run and reindex so they are grouped together
 
    # create filter summary (allows human validation for start/stop times)
    self.logging.log("info", "Generating filter Excel...")
    writer = pd.ExcelWriter(filter_summary_file, engine='xlsxwriter')
    workbook = writer.book
    
    start_row = end_row = 0
    sheet_row_count = next_sheet_row_count = 0
    sheet_count = 0
    current_sheet = 'Data' + str(sheet_count)
    sheet_legend = {}
    sorted_workloads = list(set(filter_summary['run']))
    sorted_workloads.sort()
    for name in sorted_workloads:
        #if entry['name'] not in list(filter_summary['run'].unique()) or len(filter_summary.index[filter_summary['run'] == entry['name']].tolist()) <= 1:
        #    continue

        first_row = filter_summary.index[filter_summary['run'] == name].tolist()[0]
        last_row = filter_summary.index[filter_summary['run'] == name].tolist()[-1]
        wl_rows = last_row - first_row + 1
        next_sheet_row_count += wl_rows
  
        print(name, first_row, last_row, wl_rows) if self.VERBOSE == True else 0
 
        if wl_rows >= 1e6:  # unlikely, but possible
            self.logging.log("error", "%s has %d rows => too many rows!!!"%(name, wl_rows))
            
        if next_sheet_row_count > 1e6:  # separate every million rows to new sheet
            end_row += sheet_row_count
            self.logging.log("info", "Saving df rows %d : %d to %s"%(start_row, end_row, current_sheet))
            filter_summary.iloc[start_row:end_row].to_excel(writer, sheet_name=current_sheet)
            sheet_row_count = 0
            next_sheet_row_count = last_row - first_row + 1
            start_row = end_row
            sheet_count += 1
            current_sheet = 'Data' + str(sheet_count)
            
        sheet_legend[name] = {'sheet': current_sheet, 'start': sheet_row_count+1, 'stop': next_sheet_row_count}
        sheet_row_count = next_sheet_row_count
   
    end_row += sheet_row_count
    self.logging.log("info", "Saving df rows %d : %d to %s"%(start_row, end_row, current_sheet))
    filter_summary.iloc[start_row:end_row].to_excel(writer, sheet_name=current_sheet)

    # create charts
    self.logging.log("info", "Creating filter charts...")
    workbook.add_worksheet('Charts')
    for name, placement in sheet_legend.items():
        #if entry['name'] not in sheet_legend:
        #    continue
           
        print(name, placement['sheet'], placement['start'], placement['stop']) if self.VERBOSE == True else 0
 
        df = filter_summary[filter_summary['run'] == name]
        self.add_chart(
            workbook=workbook,
            chartsheet='Charts',
            datasheet=placement['sheet'],
            df=filter_summary,
            chart_type='scatter',
            chart_subtype='smooth',
            start_row=placement['start'],
            end_row=placement['stop'],
            x_col_names='interval',
            y_col_names=['INST_RETIRED.ANY'],
            series_names=['Instructions Retired'],
            title=name,
            x_label='Interval',
            y_label='Instructions Retired',
            y_min=0,
            additional_series=[
                {
                    'name':       'Start',
                    'categories': [df.iloc[df['suggested_start'].values[0]]['interval'], df.iloc[df['suggested_start'].values[0]]['interval']],
                    'values':     [0, df['INST_RETIRED.ANY'].max()],
                    'line':       {'color': 'green'},
                    'marker':     {'type': 'none'},
                },
                {
                    'name':       'Stop',
                    'categories': [df.iloc[df['suggested_stop'].values[0]]['interval'], df.iloc[df['suggested_stop'].values[0]]['interval']],
                    'values':     [0, df['INST_RETIRED.ANY'].max()],
                    'line':       {'color': 'red'},
                    'marker':     {'type': 'none'},
                },
            ]
        )

        #self.add_chart(
        #    workbook=workbook,
        #    chartsheet='Charts',
        #    datasheet=sheet_legend[entry['name']]['sheet'],
        #    df=filter_summary,
        #    chart_type='scatter',
        #    chart_subtype='smooth',
        #    start_row=sheet_legend[entry['name']]['start'],
        #    end_row=sheet_legend[entry['name']]['stop'],
        #    x_col_names='interval',
        #    y_col_names=['metric_GFLOPS/s'],
        #    series_names=['GFLOPS/s'],
        #    title=entry['name'],
        #    x_label='Interval',
        #    y_label='GFLOPS/s',
        #    y_min=0,
        #    chart_position='right',
        #    additional_series=[
        #        {
        #            'name':       'Start',
        #            'categories': [df.iloc[df['suggested_start'].values[0]]['interval'], df.iloc[df['suggested_start'].values[0]]['interval']],
        #            'values':     [0, df['metric_GFLOPS/s'].max()],
        #            'line':       {'color': 'green'},
        #            'marker':     {'type': 'none'},
        #        },
        #        {
        #            'name':       'Stop',
        #            'categories': [df.iloc[df['suggested_stop'].values[0]]['interval'], df.iloc[df['suggested_stop'].values[0]]['interval']],
        #            'values':     [0, df['metric_GFLOPS/s'].max()],
        #            'line':       {'color': 'red'},
        #            'marker':     {'type': 'none'},
        #        },
        #    ]
        #)

        for extra_metric in added_columns:
          if df[extra_metric].isnull().all() == False:  # make sure we have that column
            self.add_chart(
              workbook=workbook,
              chartsheet='Charts',
              datasheet=placement['sheet'],
              df=filter_summary,
              chart_type='scatter',
              chart_subtype='smooth',
              start_row=placement['start'],
              end_row=placement['stop'],
              x_col_names='interval',
              y_col_names=[extra_metric],
              series_names=[extra_metric],
              title=name,
              x_label='Interval',
              y_label=extra_metric,
              y_min=0,
              chart_position='right',
              additional_series=[
                {
                  'name':       'Start',
                  'categories': [df.iloc[df['suggested_start'].values[0]]['interval'], df.iloc[df['suggested_start'].values[0]]['interval']],
                  'values':     [0, df[extra_metric].max()],
                  'line':       {'color': 'green'},
                  'marker':     {'type': 'none'},
                },
                {
                  'name':       'Stop',
                  'categories': [df.iloc[df['suggested_stop'].values[0]]['interval'], df.iloc[df['suggested_stop'].values[0]]['interval']],
                  'values':     [0, df[extra_metric].max()],
                  'line':       {'color': 'red'},
                  'marker':     {'type': 'none'},
                },
              ]
            )

    writer.save()
    
    
def combine_and_summarize(self, workloads):
    self.logging.log("info", "Combining and averaging EMON...")
    start_time = time.time()
  
    self.logging.log('info', 'Outputting summary info to %s'%(self.results_dir))
 
    # create dirs if necessary
    if os.path.isdir(self.results_dir) != True:
        subprocess.check_output("mkdir %s"%(self.results_dir), shell=True)
    flops_dir = self.results_dir + "/flops/"
    default_dir = self.results_dir + "/default/"
    memory_dir = self.results_dir + "/memory/"
    
    flops_summary_file = self.results_dir + "/flops_emon_metrics_avg.xlsx"
    default_summary_file = self.results_dir + "/default_emon_metrics_avg.xlsx"
    memory_summary_file = self.results_dir + "/memory_emon_metrics_avg.xlsx"
    
    # read in existing files
    # for now skip the combine part, it causes headaches merging data and it's easier to just overwrite
    #if os.path.exists(flops_summary_file):
    #    flops_summary = pd.read_excel(flops_summary_file, index_col=0, sheet_name='EMON', header=0)
    #else:
    flops_summary = pd.DataFrame()
        
    #if os.path.exists(default_summary_file):
    #    default_summary = pd.read_excel(default_summary_file, index_col=0, sheet_name='EMON', header=0)
    #else:
    default_summary = pd.DataFrame()
        
    #if os.path.exists(memory_summary_file):
    #    memory_summary = pd.read_excel(memory_summary_file, index_col=0, sheet_name='EMON', header=0)
    #else:
    memory_summary = pd.DataFrame()
    
    # filter and average each workload, add to summary
    for entry in workloads:
        run = entry['name']
        emon_dir = entry['emon_dir']
        metrics = entry['metrics']
        new_granularity_sec = entry['agg_secs']

        if self.INTERMEDIATE == True:
            infile = self.results_dir + "/workloads/" + run + "/%s_emon_%.3fsec_metrics.csv"%(run, new_granularity_sec)
            excel_file = self.results_dir + "/workloads/" + run + "/%s_emon_%.3fsec_metrics.xlsx"%(run, new_granularity_sec)
        else:
            infile = emon_dir + "/%s_emon_%.3fsec_metrics.csv"%(run, new_granularity_sec)
            excel_file = emon_dir + "/%s_emon_%.3fsec_metrics.xlsx"%(run, new_granularity_sec)
        
        if os.path.isfile(infile):
            whole_workload = pd.read_csv(infile, index_col=0)
        else:
            self.logging.log("warning", "Can't find %s to summarize"%(infile))
            continue
       
        # filter start/stop time
        suggested_start = whole_workload['suggested_start'].values[0]
        suggested_stop = whole_workload['suggested_stop'].values[0]
        filtered_workload = whole_workload.loc[suggested_start:suggested_stop]
    
        try:
            avg_df = filtered_workload.apply(lambda x: self.try_avg(x), axis=0)  # convert columns to numeric & avg
            avg_df['last_updated'] = str(datetime.now())
            avg_df = avg_df.rename(run)
         
            # add to summary
            if '2s.xml' in metrics or 'proxy-only.xml' in metrics or 'tmam' in metrics:
                if 'run' in default_summary and run in default_summary['run'].values:  # drop if exists
                    default_summary = default_summary.drop(default_summary[default_summary['run'] == run].index)
                default_summary = default_summary.append(avg_df)  # add it
                if os.path.isdir(default_dir) != True:
                    subprocess.check_output("mkdir %s"%(default_dir), shell=True)
                if os.path.isfile(excel_file):
                    subprocess.check_output("cp %s %s"%(excel_file, default_dir), shell=True)
            elif 'flops-only.xml' in metrics:
                if 'run' in flops_summary and run in flops_summary['run'].values:  # drop if exists
                    flops_summary = flops_summary.drop(flops_summary[flops_summary['run'] == run].index)
                flops_summary = flops_summary.append(avg_df)  # add it
                if os.path.isdir(flops_dir) != True:
                    subprocess.check_output("mkdir %s"%(flops_dir), shell=True)
                if os.path.isfile(excel_file):
                    subprocess.check_output("cp %s %s"%(excel_file, flops_dir), shell=True)
            elif 'memory-only.xml' in metrics:
                if 'run' in memory_summary and run in memory_summary['run'].values:  # drop if exists
                    memory_summary = memory_summary.drop(memory_summary[memory_summary['run'] == run].index)
                memory_summary = memory_summary.append(avg_df)  # add it
                if os.path.isdir(memory_dir) != True:
                    subprocess.check_output("mkdir %s"%(memory_dir), shell=True)
                if os.path.isfile(excel_file):
                    subprocess.check_output("cp %s %s"%(excel_file, memory_dir), shell=True)
            else:  # put it in default
                default_summary = default_summary.append(avg_df)  # add it
                if os.path.isdir(default_dir) != True:
                    subprocess.check_output("mkdir %s"%(default_dir), shell=True)
                if os.path.isfile(excel_file):
                    subprocess.check_output("cp %s %s"%(excel_file, default_dir), shell=True)
        except Exception as e:
            self.logging.log("error", "Exception %s: %s"%(sys.exc_info()[0], e)) 
        
    #create xlsx writer and save EMON data
    for file, df in [
        (flops_summary_file, flops_summary),
        (memory_summary_file, memory_summary),
        (default_summary_file, default_summary),
    ]:
       
 
    #for file, df in [(default_summary_file, default_summary)]:
        if not df.empty:
            self.logging.log("info", "Processing %s..."%(file))

            # average across runs for each workload (only group workloads whom have a 'run_count')
            if self.DISABLE_AVERAGING == False and 'run_count' in df:
                starting_workload_count = len(df)
                df['unique_workload_name'] = df.apply(lambda x: x['workload'].replace(x['run_count'],'').rstrip('-') if pd.isna(x['run_count']) == False else x['run'], axis=1)
                df = df.groupby('unique_workload_name').agg(self.try_avg)  # groupby runs, and average
                df['name'] = df.apply(lambda x: x['name'].replace(x['run_count'],'').rstrip('-') if pd.isna(x['run_count']) == False else x['name'], axis=1)
                df['run'] = df.apply(lambda x: x['run'].replace(x['run_count'],'').rstrip('-') if pd.isna(x['run_count']) == False else x['run'], axis=1)
                df['workload'] = df.apply(lambda x: x['workload'].replace(x['run_count'],'').rstrip('-') if pd.isna(x['run_count']) == False else x['workload'], axis=1)
                df['workload_index'] = df['run']
                df = df.set_index('workload_index')
                self.logging.log('info', 'Averaged across identical workload runs...reduced %d runs to %d'%(starting_workload_count, len(df)))
          
            df = df.sort_index()  # sort by workload name so they are grouped together
            df['row'] = list(range(len(df.index)))  # because index is not a number
            best_df = pd.DataFrame(columns=df.columns)
            workload_best_configs = {}  # store highest config for each workload
            workload_all_configs = {}  # store all configs for each workload
            # calculate scaling efficiencies
            df['string core freq'] = df['core freq'].apply(lambda x: self.format_core_freq(x)) # workaround because original core freq column is mixed datatype
            self.logging.log("info", "Calculating workload scaling...")
            for workload in list(df['workload'].unique()):
                all_core_freq = list(df[df['workload'] == workload]['string core freq'].unique())
                all_core_freq.sort()
                best_core_freq = all_core_freq[-2] if all_core_freq[-1] == 'default' and len(all_core_freq) > 1 else all_core_freq[-1]
                all_core_count = list(df[df['workload'] == workload]['cores used'].unique())
                all_core_count.sort()
                best_core_count = int(all_core_count[-2] if all_core_count[-1] == 'default' and len(all_core_count) > 1 else all_core_count[-1])
                all_dram_freq = list(df[df['workload'] == workload]['DRAM freq'].unique())
                all_dram_freq.sort()
                best_dram_freq = int(all_dram_freq[-2] if all_dram_freq[-1] == 'default' and len(all_dram_freq) > 1 else all_dram_freq[-1])
                workload_best_configs[workload] = {'core freq': best_core_freq, 'DRAM freq': best_dram_freq, 'cores used': best_core_count}
                workload_all_configs[workload] = {'core freq': all_core_freq, 'DRAM freq': all_dram_freq, 'cores used': all_core_count}
                
                workload_df = self.filter_df({'workload': workload, 'DRAM freq': best_dram_freq, 'cores used': best_core_count}, df)
                df.loc[df['workload'] == workload, 'core freq scaling'] = df[(df['workload'] == workload) & (df['DRAM freq'] == best_dram_freq) & (df['cores used'] == best_core_count)].apply(lambda row: self.calc_scaling(workload_df, row, 'string core freq'), axis=1)
                # core count per run
                workload_df = self.filter_df({'workload': workload, 'DRAM freq': best_dram_freq, 'core freq': best_core_freq}, df)
                df.loc[df['workload'] == workload, 'core count scaling'] = df[(df['workload'] == workload) & (df['DRAM freq'] == best_dram_freq) & (df['string core freq'] == best_core_freq)].apply(lambda row: self.calc_scaling(workload_df, row, 'cores used'), axis=1)
                # DRAM freq per run
                workload_df = self.filter_df({'workload': workload, 'cores used': best_core_count, 'core freq': best_core_freq}, df)
                df.loc[df['workload'] == workload, 'DRAM freq scaling'] = df[(df['workload'] == workload) & (df['string core freq'] == best_core_freq) & (df['cores used'] == best_core_count)].apply(lambda row: self.calc_scaling(workload_df, row, 'DRAM freq'), axis=1)
                df.loc[df['workload'] == workload, '% perf change / DRAM ns'] = df[(df['workload'] == workload) & (df['string core freq'] == best_core_freq) & (df['cores used'] == best_core_count)].apply(lambda row: self.calc_pct_change_per_val(workload_df, row, 'DRAM freq', 'metric_Average LLC data read (demand+prefetch) miss latency (in ns)'), axis=1)
                # calc efficiency as average of appropriate runs
                df.loc[df['workload'] == workload, 'core freq efficiency'] = df[df['workload'] == workload]['core freq scaling'].mean()
                df.loc[df['workload'] == workload, 'core count efficiency'] = df[df['workload'] == workload]['core count scaling'].mean()
                df.loc[df['workload'] == workload, 'DRAM freq efficiency'] = df[df['workload'] == workload]['DRAM freq scaling'].mean()
                df.loc[df['workload'] == workload, 'workload % perf change / DRAM ns'] = df[df['workload'] == workload]['% perf change / DRAM ns'].mean()
            
                # create subset df of just best configs for each workload
                best_df = best_df.append(self.filter_df({'workload': workload, 'core freq': best_core_freq, 'DRAM freq': best_dram_freq, 'cores used': best_core_count}, df), sort=False)
            
            projection_df = None
            if 'metric_FLOPS' in df:
                # create roofline flops projections data
                self.logging.log("info", "Calculating FLOPS Projections...")
                projection_df = best_df[['run', 'duration','metric_FLOPS', 'DRAM Bytes', 'Theoretical Peak DRAM GB/s', 'Theoretical Peak GFLOPS/s', 'Roofline Elbow']].copy()
                #re-calculate baseline metrics because they average differently and add error to projections
                projection_df['metric_GFLOPS/s'] = projection_df['metric_FLOPS'] / projection_df['duration'] / 1e9
                projection_df['metric_Arithmetic Intensity'] = projection_df['metric_FLOPS'] / projection_df['DRAM Bytes']
                projection_df['baseline boundedness'] = projection_df.apply(lambda row: 'memory' if row['metric_Arithmetic Intensity'] < row['Roofline Elbow'] else 'compute', axis=1)
                projection_df['Achievable Peak GFLOPS/s'] = projection_df.apply(lambda row: min(row['Theoretical Peak GFLOPS/s'], row['Theoretical Peak DRAM GB/s'] * row['metric_Arithmetic Intensity']), axis=1)
                projection_df['FP Efficiency %'] = projection_df['metric_GFLOPS/s'] / projection_df['Achievable Peak GFLOPS/s'] * 100.0
                projection_df['baseline'] = best_df['cpu_short']
                for target in projection_targets:
                    projection_df[target['name'] + ' AI'] = projection_df.apply(lambda row: (self.get_baseline_precision(row) / target['precision']) * row['metric_Arithmetic Intensity'], axis=1)
                    projection_df[target['name'] + ' Achievable GOPS'] = projection_df.apply(lambda row: min(target['peak gops'], row[target['name'] + ' AI'] * target['peak gbps']), axis=1)
                    projection_df[target['name'] + ' Realistic GOPS'] = projection_df[target['name'] + ' Achievable GOPS'] * (projection_df['FP Efficiency %'] / 100)
                    projection_df['baseline to ' + target['name']] = projection_df[target['name'] + ' Realistic GOPS'] / projection_df['metric_GFLOPS/s']
                for comparison in projection_comparisons:
                    projection_df[comparison['base'] + ' to ' + comparison['target']] = projection_df[comparison['target'] + ' Realistic GOPS'] / projection_df[comparison['base'] + ' Realistic GOPS']
            
            # create chart writer
            self.logging.log("info", "Creating Charts...")
            writer = pd.ExcelWriter(file, engine='xlsxwriter')
            workbook = writer.book
            df.to_excel(writer, sheet_name='EMON')
            best_df.to_excel(writer, sheet_name='Best Config')
            
            #create bounding box summary tab
            if set(bb_columns).issubset(df.columns):
                bb_df = best_df[bb_columns].copy()
                bb_df = bb_df.transpose()
                bb_df.to_excel(writer, sheet_name='Bounding Box')
                
            # create proxy metrics summary tab
            proxy_cols = proxy_columns + ['core freq efficiency', 'core count efficiency', 'DRAM freq efficiency', 'workload % perf change / DRAM ns']
            proxy_names = proxy_rename + ['Core Freq Eff', 'Core Count Eff', 'DRAM Freq Eff', 'perf % / DRAM ns']
            if not set(proxy_cols).issubset(df.columns):
                for column in proxy_cols:
                    if column not in best_df:
                        best_df[column] = None
            proxy_df = best_df[proxy_cols].copy()
            proxy_df.columns = proxy_names
            proxy_df = proxy_df.transpose()
            proxy_df.to_excel(writer, sheet_name='Proxy Metrics')
            
            # create flops projection summary tab
            if projection_df is not None:
                projection_df.to_excel(writer, sheet_name='FLOPS Projection')
                projection_series = []
                for comparison in projection_charts:
                    projection_series.append(comparison['base'] + ' to ' + comparison['target'])

            # create chart(s)
            start_row = 1
            end_row = len(df.index)
            workbook.add_worksheet('Charts')
            
            if projection_df is not None:
                self.add_chart(
                    workbook=workbook,
                    chartsheet='FLOPS Projection',
                    datasheet='FLOPS Projection',
                    df=projection_df,
                    chart_type='bar',
                    start_row=1,
                    end_row=len(projection_df.index),
                    x_col_names='run',
                    y_col_names=projection_series,
                    title='FLOPS Projection',
                    x_label='Perf Change',  # bar charts have x & y axis reversed
                    y_interval_unit=1,  # bar charts have x & y axis reversed
                    x_log_base=10, # bar charts have x & y axis reversed
                    y_scale=6,
                    x_scale=3,
                )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='bar',
                chart_subtype='stacked',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_TMAM_Retiring(%)',
                    'metric_TMAM_Frontend_Bound(%)',
                    'metric_TMAM_Backend_bound(%)',
                    'metric_TMAM_Bad_Speculation(%)',
                ],
                series_names=['Retiring %', 'Frontend Bound %', 'Backend Bound %', 'Bad Speculation %'],
                title='TMAM Level 1',
                x_label='% Cycles Spent', # bar charts have x & y axis reversed
                y_interval_unit=1,  # bar charts have x & y axis reversed
                gap=50,
                x_min=0,
                x_max=100,  # bar charts have x & y axis reversed
                y_scale=4,
                x_scale=3,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='bar',
                chart_subtype='stacked',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_TMAM_..Base(%)',
                    'metric_TMAM_..Microcode_Sequencer(%)',
                    'metric_TMAM_..Branch_Mispredicts(%)',
                    'metric_TMAM_..Machine_Clears(%)',
                    'metric_TMAM_..Frontend_Latency(%)',
                    'metric_TMAM_..Frontend_Bandwidth(%)',
                    'metric_TMAM_..Core_Bound(%)',
                    'metric_TMAM_..Memory_Bound(%)',
                ],
                series_names=['Retiring:Base', 'Retiring:MS-ROM', 'Bad Spec:Branch Mispredict', 'Bad Spec:Machine Clears', 'Frontend:Latency', 'Frontend:Bandwidth', 'Backend:Core', 'Backend:Memory'],
                title='TMAM Level 2',
                x_label='% Cycles Spent', # bar charts have x & y axis reversed
                y_interval_unit=1,  # bar charts have x & y axis reversed
                gap=50,
                x_min=0,
                x_max=100,  # bar charts have x & y axis reversed
                y_scale=4,
                x_scale=3,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_CPI'],
                title='',
                x_label='Configuration',
                #y_label='Cycles per Instruction',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_TMAM_Info_CoreIPC'],
                title='',
                x_label='Configuration',
                #y_label='IPC',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='stacked',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_% Uops delivered from decoded Icache (DSB)',
                    'metric_% Uops delivered from legacy decode pipeline (MITE)',
                    'metric_% Uops delivered from loop stream detector (LSD)',
                    'metric_% Uops delivered from microcode sequencer (MS)',
                ],
                series_names=['Decoded_Icache:DSB', 'legacy_decode_pipeline:MITE', 'loop_stream_detector:LSD', 'microcode_sequencer:MS'],
                title='',
                x_label='Configuration',
                #y_label='Percentage',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_CPU operating frequency (in GHz)'],
                title='',
                x_label='Configuration',
                #y_label='Frequency (GHz)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_CPU utilization %',
                    'metric_CPU utilization% in kernel mode'
                ],
                series_names=['cpu_utilization:cpu_mode','cpu_utilization:kernel_mode'],
                title='',
                x_label='Configuration',
                #y_label='CPU utilization (%)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_DTLB load MPI',
                    'metric_ITLB MPI',
                ],
                series_names=['MPI:DTLB_load','MPI:ITLB'],
                title='',
                x_label='Configuration',
                #y_label='MPI',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_FP 128-bit packed single-precision FP instructions retired per instr',
                    'metric_FP 128-bit packed double-precision FP instructions retired per instr',
                    'metric_FP 256-bit packed single-precision FP instructions retired per instr',
                    'metric_FP 256-bit packed double-precision FP instructions retired per instr',
                    'metric_FP 512-bit packed single-precision FP instructions retired per instr',
                    'metric_FP 512-bit packed double-precision FP instructions retired per instr',
                    'metric_FP scalar single-precision FP instructions retired per instr',
                    'metric_FP scalar double-precision FP instructions retired per instr',
                ],
                series_names=['128-bit:single-precision','128-bit:double-precision','256-bit:single-precision','256-bit:double-precision','512-bit:single-precision','512-bit:double-precision', 'scalar:single-precision','scalar:double-precision'],
                title='',
                x_label='Configuration',
                #y_label='FP Instructions',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_IO_bandwidth_disk_or_network_reads (MB/sec)',
                    'metric_IO_bandwidth_disk_or_network_writes (MB/sec)',
                ],
                series_names=['IO_Bandwidth:Reads', 'IO_Bandwidth:Writes'],
                title='',
                x_label='Configuration',
                #y_label='Bandwidth (MB/sec)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='stacked',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_IONUMA % disk/network reads addressed to local memory',
                    'metric_IONUMA % disk/network reads addressed to remote memory',
                ],
                series_names=['IO_NUMA_Reads:local','IO_NUMA_Reads:remote'],
                title='',
                x_label='Configuration',
                #y_label='Percentage (%)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_ItoM operations (fast strings) that miss LLC per instr',
                    'metric_ItoM operations (fast strings) that reference LLC per instr',
                ],
                title='',
                x_label='Configuration',
                #y_label='Operations',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_L1-I code read misses (w/ prefetches) per instr',
                    'metric_L1D MPI (includes data+rfo w/ prefetches)',
                    'metric_L2 MPI (includes code+data+rfo w/ prefetches)',
                    'metric_L2 demand code MPI',
                    'metric_L2 demand data read MPI',
                    'metric_LLC MPI (includes code+data+rfo w/ prefetches)',
                    'metric_LLC RFO read MPI (demand+prefetch)',
                    'metric_LLC code read MPI (demand+prefetch)',
                    'metric_LLC data read MPI (demand+prefetch)',
                ],
                series_names=['L1-I_code_read_misses', 'L1D_MPI', 'L2_MPI', 'L2_code_MPI', 'L2_data_read_MPI', 'LLC_MPI', 'LLC_RFO_read_MPI', 'LLC_code_read_MPI', 'LLC_data_read_MPI'],
                title='',
                x_label='Configuration',
                #y_label='Number',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_L2 % of L2 evictions that are NOT allocated into L3',
                    'metric_L2 % of L2 evictions that are allocated into L3',
                    'metric_L2 % of all lines evicted that are unused prefetches',
                    'metric_LLC % of LLC misses satisfied by remote caches',
                ],
                series_names=['L2_evictions_not_allocated_into_L3', 'L2_evictions_allocated_into_L3', 'lines_evicted_that_are_unused_prefetches', 'LLC_misses_satisfied_by_remote_caches'],
                title='',
                x_label='Configuration',
                #y_label='Percentage (%)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='stacked',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_L2 Any local request that HIT in a sibling core and forwarded(per instr)',
                    'metric_L2 Any local request that HITM in a sibling core (per instr)',
                    'metric_L2 all L2 prefetches(per instr)',
                ],
                series_names=['L2 Any local request that HIT in a sibling core and forwarded(per instr)', 'L2 Any local request that HITM in a sibling core (per instr)', 'L2 all L2 prefetches(per instr)'],
                title='',
                x_label='Configuration',
                #y_label='Number',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_LLC RFO references per instr (L3 prefetch excluded)',
                    'metric_LLC all LLC prefetches (per instr)',
                    'metric_LLC code references per instr (L3 prefetch excluded)',
                    'metric_LLC data read references per instr (L3 prefetch excluded)',
                    'metric_LLC total HIT clean line forwards (per instr) (excludes LLC prefetches)',
                    'metric_LLC total HITM (per instr) (excludes LLC prefetches)',
                ],
                series_names=['LLC_RFO_references_per_instr:L3_prefetch_excluded', 'LLC_prefetches_per_instr:all', 'LLC_code_reerences_per_instr:L3_prefetch_excluded', 'LLC_data_read_references_per_instr:L3_prefetch_excluded', 'LLC_total_HIT_clean_line_forwards_per_instr:LLC_prefetch_excluded', 'LLC_total_HITM_per_instr:LLC_prefetch_excluded'],
                title='',
                x_label='Configuration',
                #y_label='Number',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='stacked',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_NUMA %_RFOs addressed to local DRAM',
                    'metric_NUMA %_RFOs addressed to remote DRAM',
                ],
                series_names=['NUMA %_RFOs addressed to local DRAM', 'NUMA %_RFOs addressed to remote DRAM'],
                title='',
                x_label='Configuration',
                #y_label='Percentage (%)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='stacked',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_NUMA %_Reads addressed to local DRAM',
                    'metric_NUMA %_Reads addressed to remote DRAM',
                ],
                series_names=['NUMA %_Reads addressed to local DRAM', 'NUMA %_Reads addressed to remote DRAM'],
                title='',
                x_label='Configuration',
                #y_label='Percentage (%)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_branch mispredict ratio'],
                title='',
                x_label='Configuration',
                #y_label='Ratio',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='stacked',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_core % cycles in AVX-512 license',
                    'metric_core % cycles in AVX2 license',
                    'metric_core % cycles in non AVX license',
                ],
                series_names=['core % cycles in AVX-512 license', 'core % cycles in AVX2 license', 'core % cycles in non AVX license'],
                title='',
                x_label='Configuration',
                #y_label='Percentage (%)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_core c6 residency %',
                    'metric_package c2 residency %',
                    'metric_package c6 residency %',
                ],
                series_names=['core c6 residency', 'package c2 residency', 'package c6 residency'],
                title='',
                x_label='Configuration',
                #y_label='Number',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_stores per instr',
                    'metric_loads per instr',
                    'metric_locks retired per instr',
                ],
                series_names=['stores per instr', 'loads per instr', 'locks retired per instr'],
                title='',
                x_label='Configuration',
                #y_label='Number',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_memory bandwidth read (MB/sec)',
                    'metric_memory bandwidth write (MB/sec)',
                    'metric_memory bandwidth total (MB/sec)'
                ],
                series_names=['memory_bandwidth:read', 'memory_bandwidth:write', 'memory_bandwidth:total'],
                title='',
                x_label='Configuration',
                #y_label='Bandwidth (MB/sec)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Charts',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_core initiated local dram read bandwidth (MB/sec)',
                    'metric_core initiated remote dram read bandwidth (MB/sec)',
                ],
                series_names=['core_initiated_dram__read_bandwidth:local', 'core_initiated_dram_read_bandwidth:remote'],
                title='',
                x_label='Configuration',
                #y_label='Bandwidth (MB/sec)',
                disable_legend=False,
                y_min=0,
            )


            if len(workload_all_configs[workload]['DRAM freq']) > 1 or \
                   len(workload_all_configs[workload]['core freq']) > 1 or \
                   len(workload_all_configs[workload]['cores used']) > 1:
                    self.add_chart(
                    workbook=workbook,
                    chartsheet='Charts',
                    datasheet='EMON',
                    df=best_df,
                    start_row=start_row,
                    end_row=end_row,
                    chart_type='column',
                    x_col_names='workload',
                    y_col_names=['core freq efficiency', 'core count efficiency', 'DRAM freq efficiency'],
                    series_filters={  # will get all workloads with more than one config and use 'row' value of best_df to plot from regular df
                        'workload': [workload for workload in df['workload'].unique() if \
                                     len(workload_all_configs[workload]['DRAM freq']) > 1 or \
                                     len(workload_all_configs[workload]['core freq']) > 1 or \
                                     len(workload_all_configs[workload]['cores used']) > 1]
                    },
                    title= 'Scaling Efficiency',
            )
            
            for workload in list(df['workload'].unique()):
                next_position = 'below'
                if len(workload_all_configs[workload]['core freq']) > 1:
                    self.add_chart(
                        workbook=workbook,
                        chartsheet='Charts',
                        datasheet='EMON',
                        df=df,
                        start_row=None,
                        end_row=None,
                        chart_type='scatter',
                        x_col_names='metric_CPU operating frequency (in GHz)',
                        y_col_names=['performance'],
                        series_filters={'workload': workload, 'DRAM freq': workload_best_configs[workload]['DRAM freq'], 'cores used': workload_best_configs[workload]['cores used']},
                        title= workload + ' Core Frequency Scaling',
                        x_label='Core Frequency (GHz)',
                        y_label='Performance',
                        disable_legend=True,
                        chart_position=next_position,
                        trendline={'type': 'power', 'display_equation': True, 'display_r_squared': True},
                    )
                    next_position = 'right'
                if len(workload_all_configs[workload]['cores used']) > 1:
                    self.add_chart(
                        workbook=workbook,
                        chartsheet='Charts',
                        datasheet='EMON',
                        df=df,
                        start_row=None,
                        end_row=None,
                        chart_type='scatter',
                        x_col_names='cores used',
                        y_col_names=['performance'],
                        series_filters={'workload': workload, 'string core freq': workload_best_configs[workload]['core freq'], 'DRAM freq': workload_best_configs[workload]['DRAM freq']},
                        title= workload + ' Core Count Scaling',
                        x_label='Cores',
                        y_label='Performance',
                        disable_legend=True,
                        chart_position=next_position,
                        trendline={'type': 'power', 'display_equation': True, 'display_r_squared': True},
                    )
                    next_position = 'right'
                if len(workload_all_configs[workload]['DRAM freq']) > 1:
                    self.add_chart(
                        workbook=workbook,
                        chartsheet='Charts',
                        datasheet='EMON',
                        df=df,
                        start_row=None,
                        end_row=None,
                        chart_type='scatter',
                        x_col_names='DRAM freq',
                        y_col_names=['performance'],
                        series_filters={'workload': workload, 'string core freq': workload_best_configs[workload]['core freq'], 'cores used': workload_best_configs[workload]['cores used']},
                        title= workload + ' DRAM Frequency Scaling',
                        x_label='DRAM Frequency (MHz)',
                        y_label='Performance',
                        disable_legend=True,
                        chart_position=next_position,
                        trendline={'type': 'power', 'display_equation': True, 'display_r_squared': True},
                    )
                    next_position = 'right'
                    self.add_chart(
                        workbook=workbook,
                        chartsheet='Charts',
                        datasheet='EMON',
                        df=df,
                        start_row=None,
                        end_row=None,
                        chart_type='scatter',
                        x_col_names='metric_Average LLC data read (demand+prefetch) miss latency (in ns)',
                        y_col_names=['performance'],
                        series_filters={'workload': workload, 'string core freq': workload_best_configs[workload]['core freq'], 'cores used': workload_best_configs[workload]['cores used']},
                        title= workload + ' DRAM Latency Scaling',
                        x_label='DRAM Read Latency (ns)',
                        y_label='Performance',
                        disable_legend=True,
                        chart_position=next_position,
                        trendline={'type': 'power', 'display_equation': True, 'display_r_squared': True},
                    )
                    self.add_chart(
                        workbook=workbook,
                        chartsheet='Charts',
                        datasheet='EMON',
                        df=df,
                        start_row=None,
                        end_row=None,
                        chart_type='scatter',
                        x_col_names='DRAM freq',
                        y_col_names=['metric_Average LLC data read (demand+prefetch) miss latency (in ns)'],
                        series_filters={'workload': workload, 'string core freq': workload_best_configs[workload]['core freq'], 'cores used': workload_best_configs[workload]['cores used']},
                        title= workload + ' DRAM Latency',
                        x_label='DRAM Frequency (MHz)',
                        y_label='DRAM Read Latency (ns)',
                        disable_legend=True,
                        chart_position=next_position,
                        trendline={'type': 'power', 'display_equation': True, 'display_r_squared': True},
                    )

            if 'workload_name' in df:
                for workload in df['workload_name'].dropna().unique():
                    df_slice = df[(df['workload_name'] == workload) & (df['cores per instance'] == 1)]
                    if df_slice.empty or 'engine' not in df_slice or df_slice['engine'].isnull().values.any() or \
                       'precision' not in df_slice or df_slice['precision'].isnull().values.any():
                        #self.logging.log("info", "Not charting %s"%(workload))
                        continue
                  
                    categories = []
                    values = []
                    for index, row in df_slice.iterrows():
                        categories.append((row['engine'], row['precision']))
                        values.append(row['performance'] if not pd.isnull(row['performance']) else None)
    
                    self.add_chart(
                        workbook=workbook,
                        chartsheet='Charts',
                        datasheet='EMON',
                        df=df,
                        chart_type='column',
                        chart_subtype='stacked',
                        start_row=None,
                        end_row=None,
                        y_min=0,
                        y_max=100,
                        y_label='% Cycles',
                        x_col_names=categories,
                        y_col_names=[
                            'metric_TMAM_..Base(%)',
                            'metric_TMAM_..Microcode_Sequencer(%)',
                            'metric_TMAM_..Branch_Mispredicts(%)',
                            'metric_TMAM_..Machine_Clears(%)',
                            'metric_TMAM_..Frontend_Latency(%)',
                            'metric_TMAM_..Frontend_Bandwidth(%)',
                            'metric_TMAM_..Core_Bound(%)',
                            'metric_TMAM_..Memory_Bound(%)',
                        ],
                        series_names=['Retiring:Base', 'Retiring:MS-ROM', 'Bad Spec:Branch Mispredict', 'Bad Spec:Machine Clears', 'Frontend:Latency', 'Frontend:Bandwidth', 'Backend:Core', 'Backend:Memory'],
                        series_filters={'workload_name': workload, 'cores per instance': 1},
                        title=workload+' Model TMA & Performance',
                        additional_series=[
                            {
                                'name':       'Performance',
                                'categories': categories,
                                'values':     values,
                                'line':       None,
                                'marker':     {'type': 'circle', 'fill': {'color': 'black'}, 'border': {'color': 'black'}, 'size': 10},
                                'y2_axis':    True,
                                'type':       'scatter',
                                'y2_label':   'Throughput',
                            },
                        ]
                    )            
 

            #write to file
            writer.save()
        
    self.logging.log("info", "Finished in %d secs\n"%(time.time() - start_time))
