#!/usr/bin/env python
# coding: utf-8

import os
import time
import sys
from multiprocessing import Pool
import argparse
from datetime import datetime
import subprocess
from log import *
import traceback
import pandas as pd
import re
from glob import glob
import yaml
import math
import zipfile
import xmltodict
import shutil
import queue
from dateutil import parser

import copy
import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell


# Necessary to not truncate column data in pandas
# Used for long strings (such as HTML links) and floats (such as timestamps)
pd.set_option('display.max_colwidth', -1)



def get_args():
  parser = argparse.ArgumentParser(description="convert, aggregate, calculate metrics, and generate Excel summary & charts for raw EMON files across multiple workload runs")
  parser.add_argument("-r", "--results", default=os.getcwd()+'/emon_'+datetime.now().strftime("%Y-%m-%d_%H:%M"), help="directory to copy per-workload EMON summaries and create overall average summary")
  parser.add_argument("--suppress_logging_summary", action="store_true", help="do not generate summary of errors & warnings to the screen at the end of the run")
  parser.add_argument("-v", "--verbose", action="store_true", help="generate additional log output")
  return parser.parse_args()


def process_workload(entry):
    retval = True

    print("entry")
    print(entry)

    try:
        retval = process.convert_from_edp(entry)
    except Exception:
        logging.log("error", "Error converting %s to csv! %s"%(entry['name'], str(traceback.format_exc())))
        retval = False

    return retval 



class Workloads():

  def __init__(self, logging, verbose, results_dir):
      self.logging = logging
      self.VERBOSE = verbose
      self.results_dir = results_dir


  def get_sheet_details(self, file_path):
    sheets = []
    file_name = os.path.splitext(os.path.split(file_path)[-1])[0]
    print(file_name)
    # Make a temporary directory with the file name
    directory_to_extract_to = os.path.splitext(file_path)[0]
    print(directory_to_extract_to)
    os.mkdir(directory_to_extract_to)

    # Extract the xlsx file as it is just a zip file
    zip_ref = zipfile.ZipFile(file_path, 'r')
    zip_ref.extractall(directory_to_extract_to)
    zip_ref.close()

    # Open the workbook.xml which is very light and only has meta data, get sheets from it
    path_to_workbook = os.path.join(directory_to_extract_to, 'xl', 'workbook.xml')
    with open(path_to_workbook, 'r') as f:
        xml = f.read()
        dictionary = xmltodict.parse(xml)
        for sheet in dictionary['workbook']['sheets']['sheet']:
            sheets.append(sheet['@name'])

    # Delete the extracted files directory
    shutil.rmtree(directory_to_extract_to)
    return sheets

  def edp_list(self, entry):
      expanded_list = []
      existing_runs = {}
      root_dir = entry['search_dir']
      for root, dirs, files in os.walk(root_dir):
          path = root.split(os.sep)
          for file in files:
              file_path = root + '/' + file
              new_entry = None
              run = name = file_path.replace(root_dir, '').lstrip('/').replace('/','-').replace(' ', '-').replace('.xlsx', '').replace('emon.dat', '')

              filter_scheme = entry['filter_scheme'] if 'filter_scheme' in entry else None
              filter_start = entry['filter_start'] if 'filter_start' in entry else None
              filter_stop = entry['filter_stop'] if 'filter_stop' in entry else None
              filter_percent = entry['filter_percent'] if 'filter_percent' in entry else None
              filter_column = entry['filter_column'] if 'filter_column' in entry else None
              metrics = 'clx-2s.xml'

              if '.xlsx' in file:
                  print("file="+file_path)
                  include_file = file_path.replace(".xlsx", ".include")
                  exclude_file = file_path.replace(".xlsx", ".exclude")
                  if not os.path.isfile(include_file) and not os.path.isfile(exclude_file):
                      #xl = pd.ExcelFile(file_path)
                      xl_sheet_names = self.get_sheet_details(file_path)
                      #print(xl_sheet_names)
                      if 'emonV' not in xl_sheet_names or 'system view' not in xl_sheet_names:
                          os.mknod(exclude_file)
                          continue
                      else:
                          os.mknod(include_file)

                  if os.path.isfile(include_file):
                      new_entry = {
                          'name':           name,
                          'filter_start':   filter_start,
                          'filter_stop':    filter_stop,
                          'filter_percent': filter_percent,
                          'filter_scheme':  filter_scheme,
                          'filter_column':  filter_column,
                          'metrics':        metrics,
                          'perf':           None,
                          'agg_secs':       1.0,
                          'emon_dir':       root,
                          'edp_file':       file,
                          'node':           None,
                          'timestamp':      None,
                          'emon_bytes':     os.path.getsize(file_path),
                          'emon_created':   os.path.getmtime(file_path),
                      }
                      for key,val in entry.items():
                          if type(val) is not dict and type(val) is not list:  # don't need to add these
                              new_entry[key] = val

              if 'exclude' in entry and entry['exclude'] is not None:
                  for item in entry['exclude']:
                      exception = None
                      if isinstance(item, dict):
                          exception = item['exception'] if 'exception' in item else None
                          item = item['match'] if 'match' in item else None

                      if (exception is None and item in run) or (exception is not None and exception not in run and item in run):
                          self.logging.log('info', 'excluding %s from workloads'%(run))
                          new_entry = None
                          break

              if 'include' in entry and entry['include'] is not None:
                  match = False
                  for item in entry['include']:
                      if item in run:
                          match = True
                          break
                  if match == False:
                      self.logging.log('info', 'excluding %s from workloads'%(run))
                      new_entry = None

              if new_entry is not None:
                  expanded_list.append(new_entry)
      return expanded_list


  def create_workload_list(self, entry):
    expanded_list = self.edp_list(entry)
    
    sorted_list = sorted(expanded_list, key = lambda x: x['emon_bytes'])
    return sorted_list


# 'cursor' state for where to position chart in worksheet
chart_position_state = {}

class Process():

  def __init__(self, overwrite, verbose, results_dir, intermediate, logging, disable_averaging):
    self.OVERWRITE = overwrite
    self.VERBOSE = verbose
    self.INTERMEDIATE = intermediate
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

    
    # parse emon
    data = pd.read_excel(infile, index_col=0, sheet_name='system view', na_values=['Infinity', 'NaN'])
    data = data.transpose()
    #drop_columns = [col for col in data.columns if 'metric_' in col]
    #data = data.drop(drop_columns, axis=1)  # remove calculated metrics (they're re-calculated later)
    data = data.loc[['aggregated']]  # get just avg
    data = data.reset_index(drop=True)
    
    # write to file
    data.to_csv(outfile, chunksize=1e6)

    self.logging.log("info", "Converting %s from edp to csv took %d secs"%(run, time.time() - start_time))
    return True



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
                print("returing from add_chart here")
                return False
        else:
            if not x_col_names in columns:
                print("x-axis %s is not in columns: %s"%(x_col_names, columns))
                return False

    if not isinstance(y_col_names, list):
        y_col_names = [y_col_names]
    for y_col_name in y_col_names: 
        if not y_col_name in columns:
            print("y-axis %s is not in columns: %s"%(y_col_name, columns))
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

    #print("added chart")
    return True


# # # Combine and Summarize

# In[14]:


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


  def combine_and_summarize(self, workloads):
    self.logging.log("info", "Combining and averaging EMON...")
    start_time = time.time()
  
    self.logging.log('info', 'Outputting summary info to %s'%(self.results_dir))
 
    # create dirs if necessary
    if os.path.isdir(self.results_dir) != True:
        subprocess.check_output("mkdir %s"%(self.results_dir), shell=True)
    default_dir = self.results_dir + "/default/"
    
    default_summary_file = self.results_dir + "/default_emon_metrics_avg.xlsx"
    default_summary = pd.DataFrame()
        
    # filter and average each workload, add to summary
    for entry in workloads:
        run = entry['name']
        emon_dir = entry['emon_dir']
        metrics = entry['metrics']
        new_granularity_sec = entry['agg_secs']

        if self.INTERMEDIATE == True:
            infile = self.results_dir + "/workloads/" + run + "/" + run + "_emon_sum.csv"
            excel_file = self.results_dir + "/workloads/" + run + "/%s_emon_%.3fsec_metrics.xlsx"%(run, new_granularity_sec)
        else:
            infile = emon_dir + "/" + run + "_emon_sum.csv"
            excel_file = emon_dir + "/%s_emon_%.3fsec_metrics.xlsx"%(run, new_granularity_sec)
        
        if os.path.isfile(infile):
            whole_workload = pd.read_csv(infile, index_col=0)
        else:
            self.logging.log("warning", "Can't find %s to summarize"%(infile))
            continue
       
        try:
            avg_df = whole_workload.apply(lambda x: self.try_avg(x), axis=0)  # convert columns to numeric & avg
            #avg_df['last_updated'] = str(datetime.now())
            #avg_df['run'] = run.split("_")[0].rsplit('-',1)[0]+"-"+run.split("_")[1]+"-"+run.split("_")[2]
            avg_df['run'] = run.split("_")[0] +"-"+run.split("_")[1]+"-"+run.split("_")[2]
            avg_df = avg_df.rename(run)
            desired_order = list(avg_df.to_dict().keys())
            #print(desired_order)
         
            # add to summary
            default_summary = default_summary.append(avg_df, sort=False)  # add it
            if os.path.isdir(default_dir) != True:
                subprocess.check_output("mkdir %s"%(default_dir), shell=True)
            if os.path.isfile(excel_file):
                subprocess.check_output("cp %s %s"%(excel_file, default_dir), shell=True)
        except Exception as e:
            self.logging.log("error", "Exception %s: %s"%(sys.exc_info()[0], e)) 
        
    #create xlsx writer and save EMON data
    for file, df in [
        (default_summary_file, default_summary),
    ]:
        if not df.empty:
            self.logging.log("info", "Processing %s..."%(file))

            # create chart writer
            self.logging.log("info", "Creating Charts...")
            writer = pd.ExcelWriter(file, engine='xlsxwriter')
            workbook = writer.book
            ordered_df = df[desired_order]
            df.to_excel(writer, sheet_name='EMON')
            ordered_df.transpose().to_excel(writer, sheet_name='EDP')
            #print(ordered_df)
            

            # create chart(s)
            start_row = 1
            end_row = len(df.index)

            workbook.add_worksheet('Top Metrics Chart')
            workbook.add_worksheet('Additional Metrics Chart')
            
            #print(df)
            self.add_chart(
                workbook=workbook,
                chartsheet='Top Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
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
                #x_label='% Cycles Spent', # bar charts have x & y axis reversed
                #y_interval_unit=1,  # bar charts have x & y axis reversed
                gap=50,
                y_min=0,
                y_max=100,  # bar charts have x & y axis reversed
                x_scale=4,
                y_scale=3,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Top Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
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
                series_names=['Retiring:Base(%)', 'Retiring:MS(%)', 'Bad Spec:Branch Mispredicts(%)', 'Bad Spec:Machine Clears(%)', 'Frontend:Latency(%)', 'Frontend:Bandwidth(%)', 'Backend:Core_Bound(%)', 'Backend:Memory_Bound(%)'],
                title='TMAM Level 2',
                #x_label='% Cycles Spent', # bar charts have x & y axis reversed
                #y_interval_unit=1,  # bar charts have x & y axis reversed
                gap=50,
                y_min=0,
                y_max=100,  # bar charts have x & y axis reversed
                x_scale=4,
                y_scale=3,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_TMAM_..Memory_Bound(%)',
                    'metric_TMAM_....L1_Bound(%)',
                    'metric_TMAM_....L2_Bound(%)',
                    'metric_TMAM_....L3_Bound(%)',
                    'metric_TMAM_....MEM_Bound(%)',
                    'metric_TMAM_....Stores_Bound(%)',
                ],
                series_names=['metric_TMAM_..Memory_Bound(%)','metric_TMAM_....L1_Bound(%)', 'metric_TMAM_....L2_Bound(%)', 'metric_TMAM_....L3_Bound(%)', 'metric_TMAM_....MEM_Bound(%)', 'metric_TMAM_....Stores_Bound(%)'],
                title='TMAM Memory Bound % - Level 3',
                #x_label='% Cycles Spent', # bar charts have x & y axis reversed
                #y_interval_unit=1,  # bar charts have x & y axis reversed
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Top Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_CPI'],
                series_names=['CPI'],
                title='',
                #x_label='Configuration',
                #y_label='CPI',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Top Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_TMAM_Info_CoreIPC'],
                series_names=['TMAM_Info_CoreIPC'],
                title='',
                #x_label='Configuration',
                #y_label='IPC',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Top Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_CPU operating frequency (in GHz)'],
                series_names=['CPU operating frequency (in GHz)'],
                title='',
                #x_label='Configuration',
                #y_label='Frequency (GHz)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_branch mispredict ratio'],
                series_names=['Branch mispredict ratio'],
                title='',
                #x_label='Configuration',
                #y_label='Branch mispredict ratio',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Top Metrics Chart',
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
                series_names=['CPU utilization%','CPU utilization% in kernel mode'],
                title='',
                #x_label='Configuration',
                #y_label='CPU utilization (%)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Top Metrics Chart',
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
                series_names=['core c6 residency %', 'package c2 residency %', 'package c6 residency %'],
                title='',
                #x_label='Configuration',
                #y_label='Number',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Top Metrics Chart',
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
                #x_label='Configuration',
                #y_label='Percentage (%)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Top Metrics Chart',
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
                series_names=['128-bit packed single-precision FP instr ret per instr','128-bit packed double-precision FP instr ret per instr','256-bit packed single-precision FP instr ret per instr','256-bit packed double-precision FP instr ret per instr','512-bit packed single-precision FP instr ret per instr','512-bit packed double-precision FP instr ret per instr', 'scalar single-precision FP instr ret per instr','scalar double-precision FP instr ret per instr'],
                title='',
                #x_label='Configuration',
                #y_label='FP Instructions',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_DTLB load MPI',
                    'metric_DTLB store MPI',
                    'metric_ITLB MPI',
                ],
                series_names=['DTLB load MPI', 'DTLB store MPI', 'ITLB MPI'],
                title='',
                #x_label='Configuration',
                #y_label='MPI',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
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
                ],
                series_names=['stores per instr', 'loads per instr'],
                title='',
                #x_label='Configuration',
                #y_label='Number',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_locks retired per instr',
                    'metric_core PAUSE instr executions per instr',
                ],
                series_names=['locks retired per instr', 'core PAUSE instr executions per instr'],
                title='',
                #x_label='Configuration',
                #y_label='Number',
                disable_legend=False,
                y_min=0,
            )
            #self.add_chart(
            #    workbook=workbook,
            #    chartsheet='Additional Metrics Chart',
            #    datasheet='EMON',
            #    df=df,
            #    chart_type='column',
            #    chart_subtype='clustered',
            #    start_row=start_row,
            #    end_row=end_row,
            #    x_col_names='run',
            #    y_col_names=[
            #        'ABRPI',
            #        'BACPI',
            #        'JECPI',
            #    ],
            #    series_names=['ABRPI', 'BACPI', 'JECPI'],
            #    title='',
            #    #x_label='Configuration',
            #    #y_label='Number',
            #    disable_legend=False,
            #    y_min=0,
            #)
            self.add_chart(
                workbook=workbook,
                chartsheet='Top Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='stacked',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_memory bandwidth read (MB/sec)',
                    'metric_memory bandwidth write (MB/sec)'
                ],
                series_names=['memory_bandwidth_read (MB/s)', 'memory_bandwidth_write (MB/s)'],
                title='',
                #x_label='Configuration',
                #y_label='Bandwidth (MB/sec)',
                disable_legend=False,
                y_min=0,
            )
            #self.add_chart(
            #    workbook=workbook,
            #    chartsheet='Top Metrics Chart',
            #    datasheet='EMON',
            #    df=df,
            #    chart_type='column',
            #    chart_subtype='clustered',
            #    start_row=start_row,
            #    end_row=end_row,
            #    x_col_names='run',
            #    y_col_names=['metric_memory bandwidth utilization %'],
            #    series_names=['memory bandwidth utilization %'],
            #    title='',
            #    #x_label='Configuration',
            #    #y_label='Bandwidth (MB/sec)',
            #    disable_legend=False,
            #    y_min=0,
            #)
            self.add_chart(
                workbook=workbook,
                chartsheet='Top Metrics Chart',
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
                series_names=['%Uops delivered from Decoded_Icache (DSB)', '%Uops delivered from legacy_decode_pipeline (MITE)', '%Uops delivered from loop_stream_detector (LSD)', '%Uops delivered from microcode_sequencer (MS)'],
                title='',
                #x_label='Configuration',
                #y_label='Percentage',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Top Metrics Chart',
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
                ],
                series_names=['L1-I_code_read_misses (w/ prefetches) per instr', 'L1D_MPI (includes data+rfo w/ prefetches)', 'L2_MPI (includes code+data+rfo w/ prefetches)', 'L2_demand_code_MPI ', 'L2_demand_data_read_MPI'],
                title='',
                #x_label='Configuration',
                #y_label='Number',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Top Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_LLC MPI (includes code+data+rfo w/ prefetches)',
                    'metric_LLC RFO read MPI (demand+prefetch)',
                    'metric_LLC code read MPI (demand+prefetch)',
                    'metric_LLC data read MPI (demand+prefetch)',
                ],
                series_names=['LLC_MPI (includes code+data+rfo w/ prefetches)', 'LLC_RFO_read_MPI (demand+prefetch)', 'LLC_code_read_MPI (demand+prefetch)', 'LLC_data_read_MPI (demand+prefetch)'],
                title='',
                #x_label='Configuration',
                #y_label='Number',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
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
                series_names=['%L2_evictions_not_allocated_into_L3', '%L2_evictions_allocated_into_L3', '%lines_evicted_from_L2_that_are_unused_prefetches', '%LLC_misses_satisfied_by_remote_caches'],
                title='',
                #x_label='Configuration',
                #y_label='Percentage (%)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_L2 Any local request that HIT in a sibling core and forwarded(per instr)',
                    'metric_L2 Any local request that HITM in a sibling core (per instr)',
                ],
                series_names=['L2 Any local request that HIT in a sibling core and forwarded(per instr)', 'L2 Any local request that HITM in a sibling core (per instr)'],
                title='',
                #x_label='Configuration',
                #y_label='Number',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_L2 all L2 prefetches(per instr)',
                ],
                series_names=['L2 all L2 prefetches(per instr)'],
                title='',
                #x_label='Configuration',
                #y_label='Number',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
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
                series_names=['LLC_RFO_references_per_instr (L3_prefetch_excluded)', 'LLC_prefetches_per_instr', 'LLC_code_reerences_per_instr (L3_prefetch_excluded)', 'LLC_data_read_references_per_instr (L3_prefetch_excluded)', 'LLC_total_HIT_clean_line_forwards_per_instr (excludes_LLC_prefetches)', 'LLC_total_HITM_per_instr (excludes_LLC_prefetches)'],
                title='',
                #x_label='Configuration',
                #y_label='Number',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
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
                #x_label='Configuration',
                #y_label='Percentage (%)',
                disable_legend=False,
                y_max=100,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
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
                #x_label='Configuration',
                #y_label='Percentage (%)',
                disable_legend=False,
                y_max=100,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='stacked',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_core initiated local dram read bandwidth (MB/sec)',
                    'metric_core initiated remote dram read bandwidth (MB/sec)',
                ],
                series_names=['core_initiated_local_dram_read_bandwidth (MB/s)', 'core_initiated_remote_dram_read_bandwidth (MB/s)'],
                title='',
                #x_label='Configuration',
                #y_label='Bandwidth (MB/sec)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
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
                series_names=['IONUMA % disk/network reads addressed to local memory','IONUMA % disk/network reads addressed to remote memory'],
                title='',
                #x_label='Configuration',
                #y_label='Percentage (%)',
                disable_legend=False,
                y_max=0,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='stacked',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_IO_bandwidth_disk_or_network_reads (MB/sec)',
                    'metric_IO_bandwidth_disk_or_network_writes (MB/sec)',
                ],
                series_names=['IO_bandwidth_disk_or_network_reads (MB/sec)', 'IO_bandwidth_disk_or_network_writes (MB/sec)'],
                title='',
                #x_label='Configuration',
                #y_label='Bandwidth (MB/sec)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_TMAM_Info_L1D_Load_Miss_Latency(ns)'],
                series_names=['TMAM_Info_L1D_Load_Miss_Latency(ns)'],
                title='',
                #x_label='Configuration',
                #y_label='Bandwidth (MB/sec)',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_memory % cycles when RPQ is empty'],
                series_names=['metric_memory % cycles when RPQ is empty'],
                title='',
                #x_label='Configuration',
                #y_label='Bandwidth (MB/sec)',
                disable_legend=False,
                y_min=0,
            )  
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_memory % cycles when RPQ has 1 or more entries'],
                series_names=['metric_memory % cycles when RPQ has 1 or more entries'],
                title='',
                #x_label='Configuration',
                #y_label='Bandwidth (MB/sec)',
                disable_legend=False,
                y_min=0,
            )  
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_memory % cycles when RPQ has 10 or more entries'],
                series_names=['metric_memory % cycles when RPQ has 10 or more entries'],
                title='',
                #x_label='Configuration',
                #y_label='Bandwidth (MB/sec)',
                disable_legend=False,
                y_min=0,
            )  
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_memory % cycles when RPQ has 20 or more entries'],
                series_names=['metric_memory % cycles when RPQ has 20 or more entries'],
                title='',
                #x_label='Configuration',
                #y_label='Bandwidth (MB/sec)',
                disable_legend=False,
                y_min=0,
            )  
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_memory % cycles when RPQ has 40 or more entries'],
                series_names=['metric_memory % cycles when RPQ has 40 or more entries'],
                title='',
                #x_label='Configuration',
                #y_label='Bandwidth (MB/sec)',
                disable_legend=False,
                y_min=0,
            )  
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=['metric_UPI Data transmit BW (MB/sec) (only data)'],
                series_names=['UPI Data transmit BW (MB/sec) (only data)'],
                title='',
                #x_label='Configuration',
                #y_label='Bandwidth (MB/sec)',
                disable_legend=False,
                y_min=0,
            )  
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
                datasheet='EMON',
                df=df,
                chart_type='column',
                chart_subtype='clustered',
                start_row=start_row,
                end_row=end_row,
                x_col_names='run',
                y_col_names=[
                    'metric_core SW prefetch NTA per instr',
                    'metric_streaming stores (full line) per instr',
                    'metric_streaming stores (partial line) per instr',
                ],
                series_names=['core SW prefetch NTA per instr', 'streaming stores (full line) per instr', 'streaming stores (partial line) per instr'],
                title='',
                #x_label='Configuration',
                #y_label='Operations',
                disable_legend=False,
                y_min=0,
            )
            self.add_chart(
                workbook=workbook,
                chartsheet='Additional Metrics Chart',
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
                series_names=['ItoM operations (fast strings) that miss LLC per instr', 'ItoM operations (fast strings) that reference LLC per instr'],
                title='',
                #x_label='Configuration',
                #y_label='Operations',
                disable_legend=False,
                y_min=0,
            )


            #write to file
            writer.save()
        
    self.logging.log("info", "Finished in %d secs\n"%(time.time() - start_time))

if __name__ == "__main__":
  global logging
  global process
  global args
  args = get_args()
  logging = Log()
  process = Process(True, args.verbose, args.results, True, logging, True)
  workloads = Workloads(logging, args.verbose, args.results)
  retvals = []

  # create output dirs
  if os.path.isdir(args.results) != True:
    subprocess.check_output("mkdir %s"%(args.results), shell=True)
  if os.path.isdir(args.results + "/workloads") != True:
    subprocess.check_output("mkdir %s"%(args.results + "/workloads"), shell=True)

  absolute_start = time.time()
  workload_list = workloads.create_workload_list({'type':'edp','search_dir':args.results})
  logging.log("info", "found %d workloads in %d secs\n"%(len(workload_list), time.time() - absolute_start))

  print("workload_list")
  print(workload_list)

  if args.verbose == True:
    for workload in workload_list:
      print(workload)

  if len(workload_list) > 0:
    pool = Pool()
    retvals = pool.map(process_workload, workload_list)
    pool.close()

    process.combine_and_summarize(workload_list)

  else:
    logging.log("warning", "No workloads were processed...")


  # summarize warnings and errors to user
  warnings = logging.get_warnings()
  errors = logging.get_errors()

  if args.suppress_logging_summary == False:
    print("\n\nSummary of Warnings (%d):"%(len(warnings)))
    for num, item in enumerate(warnings):
      print("[%d]\t%s"%(num, item)) 

    print("\n\nSummary of Errors (%d):"%(len(errors)))
    for num, item in enumerate(errors):
      print("[%d]\t%s"%(num, item)) 


  successes = retvals.count(True)
  print("\n")
  logging.log("info", "Completed %d out of %d workloads successfully in %d sec\n"%(successes, len(workload_list), time.time() - absolute_start))
  
 
  # write out logs and input parameters
  log_dir = args.results + '/logs/'

  if os.path.isdir(log_dir) != True:
    subprocess.check_output("mkdir %s"%(log_dir), shell=True)

  transcript = logging.get_transcript()
  with open(log_dir + 'log.txt', 'w') as f:
    f.write("\n".join(transcript))
  with open(log_dir + 'errors.txt', 'w') as f:
    f.write("\n".join(errors))
  with open(log_dir + 'warnings.txt', 'w') as f:
    f.write("\n".join(warnings))
  with open(log_dir + 'args.txt', 'w') as f:
    print(args, file=f)

