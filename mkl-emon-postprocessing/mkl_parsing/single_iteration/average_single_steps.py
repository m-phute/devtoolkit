# usage: python average_iterations.py -d <path/to/single_iteration_logs> -s <start_iter_num> -e <end_iter_num> -c <num_lines_in_iter>

import os
import pandas
import argparse

# read and store input arguments
parser = argparse.ArgumentParser(description='Average timings for single iteration mkl verbose files')

parser.add_argument('--dir', '-d', dest='topdir', type=str, help='Directory of single iteration logs', required=True)
parser.add_argument('--start', '-s', dest='start_num', type=int, help='Starting iteration number', required=True)
parser.add_argument('--end', '-e', dest='end_num', type=int, help='Ending iteration number', required=True )
parser.add_argument('--check', '-c', dest='line_check', type=int, help='Number of lines in one iteration', required=False)

args = parser.parse_args()

topdir = args.topdir
start_num = args.start_num
end_num=args.end_num


# see if log lines verification is enabled
if args.line_check:
    line_check=args.line_check
else:
    print("Lines per log not entered. Logs will not be checked for same number of lines.")
    line_check = 0

print("topdir " + topdir)
print("start_num " + str(start_num))
print("end_num " + str(end_num))


# check if log directory exists
if not os.path.isdir(topdir):
    print("Log directory not found. Please check and re-run")
    exit()
else:
    print("Log directory found. Looking for log files...")


# create a directory for storing the averaged log file
result_dir = topdir + '/../single_iter_averaged'
if not os.path.isdir(result_dir):
    print("Creating a directory for the averaged logs")
    os.makedirs(result_dir)


dirname = topdir.split('/')[-1]
print("dirname " + dirname)


headers = ['verbose','col2','col3','col4','col5','col6','col7','col8','col9','col10','col11','col12','col13','col14','col15']

dnnl_avg_df = pandas.DataFrame()
mkldnn_avg_df = pandas.DataFrame()

dnnl_times = []
mkldnn_times = []

logs_averaged = 0


# create an array of data frames
#dnnl_dfs = {}

# average the logs
for num_log in range(start_num, end_num+1):

    num_log_3 = "{0:03}".format(num_log)

    filename = dirname + '_' + num_log_3 + '.log'


    # check if the log exists
    if not os.path.isfile(topdir + '/' + filename):
        print(filename + " not found. Please check the logs")
        exit()
    else:
        print("Processing file " + filename)

    log_df = pandas.read_csv(topdir + '/' + filename, names=headers)
    #print(log_df.head())


    # do lines verification if number of lines provided
    if line_check:
        if len(log_df.index) == line_check :
            print("Line count verified")
        else:
            print("Line count not matching, skipping file...")
            break

    # split log_df into 3 dataframes based on dnnl, mkldnn, or mkl
    dnnl_df = log_df[log_df['verbose'] == 'dnnl_verbose']
    mkldnn_df = log_df[log_df['verbose'] == 'mkldnn_verbose']
    mkl_df = log_df[log_df['verbose'].str.contains('MKL_VERBOSE')]

    #print(dnnl_df.head())
    #print(mkldnn_df.head())
    #print(mkl_df.head())


    # Get the first non-time columns in a df and add the times column to a common list
    if num_log == start_num:

        dnnl_common_columns = ['verbose','col2','col3','col4','col5','col6','col7','col8','col9','col10']
        dnnl_avg_df = dnnl_df[dnnl_common_columns]
        dnnl_times = dnnl_df['col11']
        #dnnl_times = list(map(float, dnnl_times))
        #print(dnnl_avg_df.head())
        #print(dnnl_times)

        mkldnn_common_columns = ['verbose','col2','col3','col4','col5','col6','col7','col8']
        mkldnn_avg_df = mkldnn_df[mkldnn_common_columns]
        mkldnn_times = mkldnn_df['col9']
        #mkldnn_times = list(map(float, mkldnn_times))
        #print(mkldnn_avg_df.head())
        #print(mkldnn_times)


    # Add the timing values column to a common list
    else :

        #dnnl_times = dnnl_times + list(map(float, dnnl_df['col11']))
        #mkldnn_times = mkldnn_times + list(map(float, mkldnn_df['col9']))

        dnnl_times = [float(a) + float(b) for a,b in zip(dnnl_times, dnnl_df['col11'])]
        mkldnn_times = [float(a) + float(b) for a,b in zip(mkldnn_times, mkldnn_df['col9'])]

        #print(dnnl_times)
        #print(mkldnn_times)

print(dnnl_times)
print(mkldnn_times)


# Average 'dnnl_times' and 'mkldnn_times' list based on the number of logs
dnnl_times[:] = [float(x) / (end_num - start_num + 1) for x in dnnl_times]
dnnl_times = [ '%.6f' % elem for elem in dnnl_times ]
#print(dnnl_times)
print(len(dnnl_times))

mkldnn_times[:] = [float(x) / (end_num - start_num + 1) for x in mkldnn_times]
mkldnn_times = [ '%.6f' % elem for elem in mkldnn_times ]
#print(mkldnn_times)
print(len(mkldnn_times))


# Add the averaged list to the avgeraged dataframe
print(len(dnnl_avg_df))
print(len(mkldnn_avg_df))
dnnl_avg_df['col11'] = dnnl_times
mkldnn_avg_df['col9'] = mkldnn_times

# Merge the 3 dfs and sort based on index
avg_df = pandas.concat([dnnl_avg_df, mkldnn_avg_df, mkl_df], sort=False)
avg_df = avg_df.sort_index()
#avg_df = avg_df[headers]
print(avg_df.head())


# Write to a csv
avg_file_name = result_dir + '/' + dirname + '_singleIter.log'
print('Writing to csv at ' + avg_file_name)
avg_df.to_csv(avg_file_name, header=False, index=False)

