# Get a csv for frequency from processed edp excel files

# usage: python get_edp_freq.py /path/to/processed_edp_excel_files

import os
import os.path
import sys
import xlsxwriter
import xlrd
import openpyxl
import pandas
import multiprocessing
from multiprocessing import Pool

topdir = sys.argv[1]
edppath = topdir + '/edp_freq.csv'

parallel_processes = 36

if os.path.isfile(edppath):
    print("\n" + edppath + " found. Please remove/delete and re-run")
    exit()
else:
    print(edppath + " not found. Creating file")
    df = pandas.DataFrame(columns=["Config","Frequency"])

def parse_freq(edp_list):

    config = filename.rsplit("_",2)[0]
    edp_excel = pandas.read_excel(topdir + '/' + filename, sheet_name="system view")
    row_to_add = ['', '']

    for index, row in edp_excel.iterrows():
        if row[0] == "metric_CPU operating frequency (in GHz)":
            row_to_add[0] = config
            row_to_add[1] = row[1]

            #print(row_to_add)
            break
    
    #df.loc[len(df)] = row_to_add
    return row_to_add

edp_list = []

for filename in os.listdir(topdir):
    if filename.split('.')[-1] == 'xlsx':
        edp_list.append(filename)

pool = Pool(parallel_processes)
edp_data = pool.map(parse_freq, edp_list)
pool.close()

df = pandas.DataFrame(edp_data, columns=["Config","Frequency"])
print(df)
df.to_csv(edppath, index=False)
