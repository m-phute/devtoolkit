# Script to parse Raritan power logs
# For details/changes please contact Madhuri Phute (madhuri.phute@intel.com)

import time
import os
import re
import sys
import pandas
import pathlib
from datetime import datetime

log_path = f'C:\\Users\\lab_uhsusr\\Documents\\Raritan\\oobPowerCheckout_tfTopologies'

def parse_power_data():

  df_summary = pandas.DataFrame()

  for file in os.listdir(log_path):
  
    if (pathlib.Path(file).suffix == ".xlsx") and (file != "summary.xlsx") :
      
      df_file = pandas.read_excel(f'{log_path}\{file}')
      df_file.rename({'Active Power': file}, axis=1, inplace=True)
      
      df_summary = pandas.concat([df_summary, df_file[file]], axis=1)
      
    else:
      print(f"Excluding {file}")
    
  print("Writing to excel")
  df_summary.to_excel(f"{log_path}\summary.xlsx", sheet_name='Raw Data')


load_time = datetime.now()
print(f"power_collection_raritan.py loaded successfully at {load_time}")