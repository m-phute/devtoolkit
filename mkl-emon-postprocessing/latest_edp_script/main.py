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
from workloads import *
from process import *
import traceback


def get_args():
  parser = argparse.ArgumentParser(description="convert, aggregate, calculate metrics, and generate Excel summary & charts for raw EMON files across multiple workload runs")
  parser.add_argument("-y", "--yaml", help="input workload yaml (use one flag for each input yaml)", required=True, action='append')
  parser.add_argument("-r", "--results", default=os.getcwd()+'/emon_'+datetime.now().strftime("%Y-%m-%d_%H:%M"), help="directory to copy per-workload EMON summaries and create overall average summary")
  parser.add_argument("-i", "--intermediate", action="store_true", help="store intermediate files in your results directory, otherwise they go to the original EMON directory")
  parser.add_argument("-a", "--aibt", action="store_true", help="attempt to match EMON runs with results on the AIBT dashboard (will prompt for username/password)")
  parser.add_argument("-f", "--filter_summary", action="store_true", help="generate filter summary xlsx to show start & stop times chosen for each workload")
  parser.add_argument("-s", "--no_summary", action="store_true", help="do not generate summary xlsx of all workload runs")
  parser.add_argument("--suppress_logging_summary", action="store_true", help="do not generate summary of errors & warnings to the screen at the end of the run")
  parser.add_argument("-p", "--per_core", action="store_true", help="generate per-core EMON csv for each workload run (does not aggregate or add metrics yet); !!WARNING may take a long time!!")
  parser.add_argument("-v", "--verbose", action="store_true", help="generate additional log output")
  parser.add_argument("-o", "--overwrite", action="store_true", help="overwrite existing results if they exist")
  parser.add_argument("-d", "--dry_run", action="store_true", help="generate list of workloads that would be processed but don't process")
  parser.add_argument("--disable_averaging", action="store_true", help="do not average across multiple identical workload runs; treat as separate workloads")
  parser.add_argument("--no_convert", action="store_true", help=argparse.SUPPRESS)
  parser.add_argument("--no_aggregate", action="store_true", help=argparse.SUPPRESS)
  parser.add_argument("--no_metrics", action="store_true", help=argparse.SUPPRESS)
  parser.add_argument("--no_excel", action="store_true", help=argparse.SUPPRESS)
  return parser.parse_args()


def process_workload(entry):
    retval = True

    print("entry")
    print(entry)

    if args.no_convert == False:
        try:
            retval = process.convert_to_csv(entry)
        except Exception:
            logging.log("error", "Error converting %s to csv! %s"%(entry['name'], str(traceback.format_exc())))
            retval = False

    if args.no_aggregate == False and retval == True:    
        try:
            retval = process.aggregate(entry)
        except Exception:
            logging.log("error", "Error aggregating %s! %s"%(entry['name'], str(traceback.format_exc())))
            retval = False
  
    if args.no_metrics == False and retval == True:  
        try:
            retval = process.calculate_metrics(entry)
        except Exception:
            logging.log("error", "Error calculating metrics for %s! %s"%(entry['name'], str(traceback.format_exc())))
            retval = False

    if args.no_excel == False and retval == True:    
        try:
            retval = process.create_excel(entry)
        except Exception:
            logging.log("error", "Error creating excel for %s! %s"%(entry['name'], str(traceback.format_exc())))
            retval = False

    return retval 


if __name__ == "__main__":
  global logging
  global process
  global args
  args = get_args()
  logging = Log()
  process = Process(args.overwrite, args.per_core, args.verbose, args.results, args.intermediate, args.aibt, logging, args.disable_averaging)
  workloads = Workloads(logging, args.verbose, args.results)
  retvals = []

  # create output dirs
  if os.path.isdir(args.results) != True:
    subprocess.check_output("mkdir %s"%(args.results), shell=True)
  if args.intermediate == True:
    if os.path.isdir(args.results + "/workloads") != True:
      subprocess.check_output("mkdir %s"%(args.results + "/workloads"), shell=True)

  absolute_start = time.time()
  workload_list = workloads.get_workloads(args.yaml)
  logging.log("info", "found %d workloads in %d secs\n"%(len(workload_list), time.time() - absolute_start))

  print("workload_list")
  print(workload_list)

  if args.verbose == True:
    for workload in workload_list:
      print(workload)

  if args.aibt == True:
    process.aibt_login()

  if len(workload_list) > 0 and args.dry_run == False:
    pool = Pool()
    retvals = pool.map(process_workload, workload_list)
    pool.close()

    if args.no_summary == False:
      process.combine_and_summarize(workload_list)

    if args.filter_summary == True:
      process.create_filter_summary(workload_list)
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
  yaml_dir = args.results + '/yamls/'

  if os.path.isdir(log_dir) != True:
    subprocess.check_output("mkdir %s"%(log_dir), shell=True)
  if os.path.isdir(yaml_dir) != True:
    subprocess.check_output("mkdir %s"%(yaml_dir), shell=True)


  transcript = logging.get_transcript()
  with open(log_dir + 'log.txt', 'w') as f:
    f.write("\n".join(transcript))
  with open(log_dir + 'errors.txt', 'w') as f:
    f.write("\n".join(errors))
  with open(log_dir + 'warnings.txt', 'w') as f:
    f.write("\n".join(warnings))
  with open(log_dir + 'args.txt', 'w') as f:
    print(args, file=f)

  for item in args.yaml:
    subprocess.check_output("cp %s %s"%(item, yaml_dir), shell=True)

