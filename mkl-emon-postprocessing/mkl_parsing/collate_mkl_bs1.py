import os
import os.path
import sys
import xlsxwriter
import xlrd
import openpyxl
import pandas


topdir = sys.argv[1]

print("directory being processed " + topdir)

# Create new excel sheet with rows if it doesn't exist
filepath = topdir + '/all_instance_summary.xlsx'

if not os.path.isfile(filepath):

    print(filepath + " not found. Creating file")
    writer = pandas.ExcelWriter(filepath, engine='xlsxwriter')
    
    stats_sheet = pandas.DataFrame(columns=["Metric"], data=["MKLDNN_execution_sec", "MKL_MKLDNN_execution_sec", "MKL_execution_sec", "dram_channels", "freq", "ideal_macspersec", "non_verbose_workload_wallclock_sec", "num_cores", "peak_gbps", "peak_gops", "roofline_intensity", "sum_weighted_efficiency_%", "time_%_outside_mkl_mkldnn", "time_sec_outside_mkl_mkldnn", "tmul_workload_speedup_%", "vector_units_per_core", "verbose_workload_wallclock_sec", "workload"])

    primitives_sheet = pandas.DataFrame(columns=['Operation'], data=["convolution", "other", "reorder", "pooling", "eltwise", "inner_product", "softmax"])


else:
    print("\n" + filepath + " found. Please remove/delete and re-run")
    exit()


# Iterate through all instances and add data to it's own column
colOrder_stats = []
colOrder_primitives = []
newOrder_primitives = []

for filename in os.listdir(topdir):
    
    if filename != 'all_instance_summary.xlsx':
        
        print(filename)
        ins_num = filename.split('_')[0].split('-')[-1].split('s')[1]

        # Adding the Stats sheet
        singleIns_stats = pandas.read_excel(topdir + '/' + filename, sheet_name="Stats")

        colOrder_stats.append(ins_num) 
        
        singleIns_stats.columns = ['Metric', ins_num]
        #singleIns_stats = singleIns_stats.drop('A', axis=1)
        
        stats_sheet = stats_sheet.join(singleIns_stats[ins_num])

        
        # Adding the Primitives sheet
        singleIns_primitives = pandas.read_excel(topdir + '/' + filename, sheet_name="Primitives")
        
        colOrder_primitives.append(ins_num)
        
        singleIns_primitives.columns = ['Operation', ins_num + ', count', ins_num + ', time_%', ins_num + ', time_ms']

        primitives_sheet = pandas.merge(primitives_sheet, singleIns_primitives)
        #primitives_sheet = primitives_sheet.join(singleIns_primitives)
        


colOrder_stats.sort(key=int)
colOrder_stats.insert(0, 'Metric')
stats_sheet = stats_sheet[colOrder_stats]
stats_sheet.to_excel(writer, sheet_name='Stats', index=False)

colOrder_primitives.sort(key=int)
colOrder_primitives.insert(0,'')
a = primitives_sheet.columns.str.split(', ', expand=True).values
primitives_sheet.columns = pandas.MultiIndex.from_tuples([('', x[0]) if pandas.isnull(x[1]) else x for x in a])
primitives_sheet = primitives_sheet[colOrder_primitives]
primitives_sheet.to_excel(writer, sheet_name='Primitives')

writer.save()


