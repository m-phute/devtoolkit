import subprocess
import json
import getpass
import datetime
from dateutil import parser
import pandas as pd
import xlsxwriter
import logging


aibt_map = [
  {  # production aibt
    'framework': {'tensorflow': '3'},
    'engine': {'mkldnn': '3', 'eigen': '30'}, 
    'network_model': {  # workload
      'resnet_50_v1_5': '409',
      'dcgan': '90',
      'fasterrcnn_resnet_50_v1': '276',
      'inception_v3': '6',
      'maskrcnn_resnet_101_v1': '318',
      'ncf': '333',
      'resnet_101_v1': '75',
      'resnet_50_v1': '63',
      'rfcn_resnet_101': '336',
      'ssd_resnet_34': '446',
      'ssd_vgg16': '252',
      'wavenet': '388',  # deepmind_wavenet
      #'wavenet': '213',
      'densenet_169': '150',
      'draw': '210',
      'facenet': '372',
      'gnmt_4': '357',
      'inception_resnet_v2': '168',
      'inception_v4': '96',
      'ssd_mobilenet_v1': '48',
      'mobilenet_v1': '114',
      'mtcc': '378',
      'unet': '234',
      'wide_and_deep': '180',
      'wide_n_deep': '180',
    },
    'data_type': {'float32': '3', 'int8': '6'},  # precision
    'origin_team': {'aibench': '46'},
  },
  {  # dev aibt
    'framework': {'tensorflow': '3'},
    'engine': {'mkldnn': '3', 'eigen': '25'}, 
    'network_model': {  # workload
      'resnet_50_v1_5': '37',
      'dcgan': '42',
      'fasterrcnn_resnet_50_v1': '211',
      'inception_v3': '6',
      'maskrcnn_resnet_101_v1': '280',
      'ncf': '370',
      'resnet_101_v1': '70',
      'resnet_50_v1': '47',
      'rfcn_resnet_101': '323',
      'ssd_resnet_34': '418',
      'ssd_vgg16': '298',
      'wavenet': '356',  # deepmind_wavenet
      #'wavenet': '265',
      'densenet_169': '136',
      'draw': '250',
      'facenet': '417',
      'gnmt_4': '175',
      'inception_resnet_v2': '169',
      'inception_v4': '85',
      'ssd_mobilenet_v1': '35',
      'mobilenet_v1': '103',
      'mtcc': '374',
      'unet': '253',
      'wide_and_deep': '172',
      'wide_n_deep': '172',
    },
    'data_type': {'float32': '2', 'int8': '5'},  # precision
    'origin_team': {'aibench': '18'},
  }
]

# search both production and dev dashboards (production first)
login_urls = ['https://aibt.app.intel.com/json/v1/auth', 'https://devaibt.app.intel.com/json/v1/auth']
curl_urls = ['https://aibt.app.intel.com/json/v1/benchmark_inference?', 'https://devaibt.app.intel.com/json/v1/benchmark_inference?']
user_urls = ['https://aibt.app.intel.com/results/benchmark_inference', 'https://devaibt.app.intel.com/results/benchmark_inference']
util_urls = ['https://aibt.app.intel.com/json/v1/benchmark_inference_utilization', 'https://devaibt.app.intel.com/json/v1/benchmark_inference_utilization']

def aibt_login(self):
  print("\nPlease enter AIBT dashboard login username & password:") 
  username = input("\tUsername: ")
  password = getpass.getpass("\tPassword: ")
  print("")

  for idx, url in enumerate(login_urls):
    curl_cmd = "'%s' -H 'Content-Type: application/vnd.api+json' --data '{\"username\":\"%s\",\"password\":\"%s\"}'"%(url, username, password)
    result = subprocess.check_output("curl -k %s"%(curl_cmd), shell=True, stderr=subprocess.DEVNULL)
    values = json.loads(result)

    if 'token' in values and values['token'] is not None and values['token'] != "":
      self.tokens[idx] = values['token']
      self.logging.log("info", "successful login to %s"%(url)) 
    else:
      self.tokens[idx] = 0  # failed
      self.logging.log("error", "failed login to %s"%(url)) 


def match_aibt_timestamp(self, emon_row, per_interval_mem_util, aibt_emon_timestamp_offset_sec, mem_val_name, mem_val_type):
  emon_time = parser.parse(emon_row['timestamp'], ignoretz=True) + datetime.timedelta(seconds=aibt_emon_timestamp_offset_sec)
  for index,interval in enumerate(per_interval_mem_util):
    aibt_start_time = parser.parse(interval['start_date'], ignoretz=True)
    aibt_stop_time = parser.parse(per_interval_mem_util[index+1]['start_date'], ignoretz=True) if (index+1) < len(per_interval_mem_util) else parser.parse(interval['stop_date'], ignoretz=True)
    #print("testing", emon_row['timestamp'], aibt_emon_timestamp_offset_sec, emon_time, interval['start_date'], interval['stop_date'])
    if emon_time >= aibt_start_time and emon_time <= aibt_stop_time:
      #print("\tmatch", emon_time, interval['start_date'], interval['stop_date'])
      #self.logging.log('info', 'Found time match!')
      return interval[mem_val_name][mem_val_type]

  #print("\tno match", emon_time)
  return None


def aibt_search(self, df):
  if self.AIBT == True and self.tokens[0] is None and self.tokens[1] is None:
    self.aibt_login()

  if self.AIBT == True and (self.tokens[0] != 0 or self.tokens[1] != 0):
    # should be called on individual workloads, so just grab first row
    row = df.iloc[0]
    workload = row['workload']
    if 'timestamp' in row and row['timestamp'] is not None and pd.isnull(row['timestamp']) == False:
      parsed_emon_date = parser.parse(row['timestamp'])
      # search AIBT dashboard for +/- one day from EMON timestamp because dates in AIBT are inconsistent and might be off by 8hrs or 0hrs
      # this is likely due to poor timezone conversion handling and only affects the date search. Results will later be sorted by time.
      search_date_start = (parsed_emon_date - datetime.timedelta(days=1)).strftime("%m/%d/%Y")
      search_date_end = (parsed_emon_date + datetime.timedelta(days=1)).strftime("%m/%d/%Y")
    else:
      #print("No timestamp for %s"%(workload))
      return df

  
    match = False
    for url_idx, curl_url in enumerate(curl_urls):
      if self.tokens[url_idx] == 0 or match == True:
        continue

      framework = aibt_map[url_idx]['framework']['tensorflow']
      origin_team = aibt_map[url_idx]['origin_team']['aibench']
      engine = row['engine'] if 'engine' in row else None
      data_type = row['precision'] if 'precision' in row else None
      network_model = None
      workload_string = workload.lower()

      if pd.isnull(engine) == False:
        workload_string = workload_string.replace(engine, '')
      if pd.isnull(data_type) == False:
        workload_string = workload_string.replace(data_type, '')
      workload_string = workload_string.replace('-', '')

      if pd.isnull(engine):
        for key,value in aibt_map[url_idx]['engine'].items():
          if key in workload_string:
            #print("WARN: matching %s with %s"%(key, workload))
            engine = value
            df['engine'] = key
      elif engine in aibt_map[url_idx]['engine']:
        engine = aibt_map[url_idx]['engine'][engine]
      else:
        self.logging.log("error", "invalid aibt engine %s for %s"%(engine, workload))
        continue

      if pd.isnull(data_type):
        for key,value in aibt_map[url_idx]['data_type'].items():
          if key in workload_string:
            #print("WARN: matching %s with %s"%(key, workload))
            data_type = value
            df['precision'] = key
      elif data_type in aibt_map[url_idx]['data_type']:
        data_type = aibt_map[url_idx]['data_type'][data_type]
      else:
        self.logging.log("error", "invalid aibt data_type %s for %s"%(data_type, workload))
        continue

      if pd.isnull(engine):
        engine = aibt_map[url_idx]['engine']['mkldnn']  # if still don't have it, assume default mkldnn
        df['engine'] = 'mkldnn'
      if pd.isnull(data_type):
        data_type = aibt_map[url_idx]['data_type']['float32']  # if still don't have it, assume default float32
        df['precision'] = 'float32'

      for key,value in aibt_map[url_idx]['network_model'].items():
        if key.replace('_', '') == workload_string:
          network_model = value
          break
        elif key.replace('_', '') in workload_string:
          #print("WARN: matching %s with %s"%(key, workload))
          network_model = value
          df['workload_name'] = key.replace('_', '-') if 'workload_name' not in row or pd.isnull(row['workload_name']) else df['workload_name']
          break

      if network_model is None or engine is None or data_type is None or \
         pd.isnull(network_model) or pd.isnull(engine) or pd.isnull(data_type):
        #self.logging.log("info", "Do not have all required fields for %s (%s): %s, %s, %s"%(workload, workload_string, engine, data_type, network_model))
        continue

      filters = {
        'response_type': '',
        'selectedResultId': '',
        'start': '0',
        'length': '50',
        'search': {'value': '', 'regex': 'false'},
        'origin_team': [origin_team],
        'engine': [engine],
        'network_model': [network_model],
        'data_type': [data_type],
        'datepicker_range': [search_date_start, search_date_end]
      }


      user_url = user_urls[url_idx]
      for idx,(key,value) in enumerate(filters.items()):
        if idx > 0: curl_url += '&'

        if type(value) in [dict]:
          for i,(k,v) in enumerate(value.items()):
            if i > 0: curl_url += '&'
            curl_url += 'filter\[queryParams\]\[' + key + '\]\[' + k + '\]=' + v
        elif type(value) in [list]:
          user_url += ';' + key + '='
          for i,v in enumerate(value):
            if i > 0: 
              user_url += ','
              curl_url += '&'
            user_url += v.replace('/', '%2F')
            curl_url += 'filter\[queryParams\]\[' + key + '\]\[' + str(i) + '\]=' + v
        else:
          curl_url += 'filter\[queryParams\]\[' + key + '\]=' + value

      curl_cmd = "'%s' -H 'Authorization: Bearer %s'"%(curl_url, self.tokens[url_idx])
      result = subprocess.check_output("curl -k %s"%(curl_cmd), shell=True, stderr=subprocess.DEVNULL)
      values = json.loads(result)

      if 'data' not in values or len(values['data']) == 0:
        #self.logging.log("info", "No AIBT results in search for %s: %s"%(workload, user_url))
        continue

      #self.logging.log("info", "Found AIBT results for %s: %s"%(workload, user_url))
      match = True
      closest_diff = None
      closest_idx = None

      for idx,entry in enumerate(values['data']):
        date = entry['attributes']['testStartTime']['date']

        if len(values['data']) == 1:  # if only one result, take it
          closest_idx = 0
        else:  # more than one, take closest time
          parsed_aibt_date = parser.parse(date)
          diff = abs((parsed_emon_date - parsed_aibt_date).total_seconds())
          if closest_diff is None or diff < closest_diff:
            closest_diff = diff
            closest_idx = idx 

      if closest_idx is not None:
        entry = values['data'][closest_idx]
        id = entry['id']
        jobuuid = entry['attributes']['jobUuid']
        throughput = entry['attributes']['summaryFps']
        latency = entry['attributes']['summaryMs']
        date = entry['attributes']['testStartTime']['date']

        #print("MATCH!", jobuuid, date, id, throughput)
        #print("\t", user_url)

        if 'performance' in df and pd.isnull(row['performance']) == False:
          self.logging.log("warning", "%s overwriting existing performance of %s with %s from aibt"%(workload, row['performance'], throughput))

        df['performance'] = throughput
        df['perf'] = throughput
        df['aibt_dashboard'] = user_url
        df['aibt_data'] = curl_urls[url_idx] + 'filter[id]=' + id


        # use jobuuid to get utilization info
        util_url = util_urls[url_idx] + '/' + jobuuid
        util_cmd = "'%s' -H 'Authorization: Bearer %s'"%(util_url, self.tokens[url_idx])
        result = subprocess.check_output("curl -k %s"%(util_cmd), shell=True, stderr=subprocess.DEVNULL)
        values = json.loads(result)

        if 'hits' not in values:  # empty json
          continue

        #self.logging.log('info', 'Found utilization for %s!'%(workload))

        per_interval_per_cpu_util = values['hits']['hits'][0]['_source']['json']['data'][0]['data']  # can be used later if we want to look at per-cpu util outside of EMON
        per_interval_mem_util = values['hits']['hits'][0]['_source']['json']['data'][1]['data']
        #mem_util_vals = {'active': {'maximum': 0}, 'available': {'minimum': 0}, 'cached': {'maximum': 0}, 'total': {'maximum': 0}}

        # find timestamp offset between EMON & AIBT
        aibt_start_timestamp = parser.parse(per_interval_mem_util[0]['start_date'], ignoretz=True)
        emon_start_timestamp = parser.parse(df.iloc[df['suggested_start'].values[0]]['timestamp'], ignoretz=True) # first interval of workload
        #emon_start_timestamp = parser.parse(df['timestamp'].values[0], ignoretz=True) # first interval of emon
        aibt_emon_timestamp_offset_sec = (aibt_start_timestamp - emon_start_timestamp).total_seconds()

        df['aibt_max_active_mem'] = df.apply(lambda x: self.match_aibt_timestamp(x, per_interval_mem_util, aibt_emon_timestamp_offset_sec, 'active', 'maximum'), axis=1)
        df['aibt_max_cached_mem'] = df.apply(lambda x: self.match_aibt_timestamp(x, per_interval_mem_util, aibt_emon_timestamp_offset_sec, 'cached', 'maximum'), axis=1)
        df['aibt_min_available_mem'] = df.apply(lambda x: self.match_aibt_timestamp(x, per_interval_mem_util, aibt_emon_timestamp_offset_sec, 'available', 'minimum'), axis=1) 
 
  
  return df 

