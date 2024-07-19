This document describes how to post process mkl verbose enabled logs and edp processed excel sheets. Please contact Madhuri Phute (madhuri.phute@intel.com) for any questions.

There are 2 different types of post-processing techniques available:

 - EMON post processing
 - MKL post processing

**PRE-REQUISITES**

It is recommended that the user create a virtual environment to install the dependencies.

`$ virtualenv -p python3 env_postProcess`

`$ source env_postProcess/bin/activate`

`$ pip install -r requirements.txt`

**MKL Post Processing**

The scripts for MKL post-processing are in `mkl-emon-postprocessing/mkl_parsing/`

For processing MKL logs, he following timing and frequency csv files are needed:

*  `timing_verbose.csv` - A list of the inference times from the mkl logs for entire run
*  `timing_verbose_singleIter.csv` - A list of the inference times from the mkl logs for a single iteration
*  `timing_nonVerbose.csv` - A list of inference times from baseline logs
*  `timing_nonVerbose_singleIter.csv` - A list of the inference times from baseline logs for a single iteration
*  `edp_freq.csv` - A list of frequencies from the processed edp excel sheets

Please see the post-processing steps of the respective topology to generate the timing files.

The `edp_freq.csv` file can be generated using the `get_edp_freq.py` script. Processed edp excel files are required for this stage. If you want to process without that, please contact Madhuri Phute (madhuri.phute@intel.com)

1. MKL Processing for entire run

Modify lines 39-41 of `mkl_verbose.py` and `mkl_verbose_singleIter.py` to point to the respective timing and csv files.

`$ python mkl_verbose.py /path/to/mkl/directories`

This will give the processed files for every config in a 'results' sub-directory within the mkl directory. This also contains the cross-workload file.

2. MKL Processing for single iteration

The user needs to first check how many lines correspond to a single iteration and modify lines 20 and 25 of `wrapper_mkl_parsing.sh` accordingly.

`$ python mkl_verbose_singleIter.py /path/to/mkl/directories`

This will give the processed files for every config in a 'results_singleIter' sub-directory within the mkl directory. This does not contain the cross-workload file.

**EMON Post Processing**

The scripts for EMON charting are in `mkl-emon-postprocessing/telemetry_processing/`

This requires all the edp processed excel files to be in a single directory.

Modify the 'search_dir' path in `yamls/cwr.yaml` to point to the directory containing the excel files.

`$ python main.py -y /path/to/cwr.yaml -r /path/to/store/results --intermediate --overwrite`

The processed files will be stored in the specified results directory.