import pandas as pd
import re
import os
from glob import glob
import yaml
import log
import subprocess

class Workloads():

  def __init__(self, logging, verbose, results_dir):
      self.logging = logging
      self.VERBOSE = verbose
      self.results_dir = results_dir


  def get_workloads(self, list_of_yamls):
      if type(list_of_yamls) is not list:
          self.logging.log('error', 'expected a list of yaml file paths')
          return []
      else:
          self.logging.log('info', 'generating list of workloads to process...')

      workload_list = []

      for yaml_file in list_of_yamls:
          if os.path.isfile(yaml_file) == False:
              self.logging.log('error', 'could not find input yaml %s'%(yaml_file))
              continue

          self.logging.log('info', 'processing yaml %s'%(yaml_file))
          with open(yaml_file) as f:
              docs = yaml.load(f, Loader=yaml.SafeLoader)
              for doc in docs:
                  for name, values in doc.items():
                      self.logging.log('info', 'processing workload set %s'%(name))
                      
                      if type(values) is dict and 'type' in values:  # search type
                          workload_list += self.create_workload_list(values)
                      elif type(values) is list:
                          if type(values[0]) is dict and 'name' in values[0]: # explicit list of workloads
                              workload_list += values
                          elif '.yaml' in values[0]:  # list of yamls to include
                              workload_list += self.get_workloads(values)
                      else:
                          self.logging.log('error', 'unexpected workload format %s for %s:\t%s'%(type(values), name, values))


      # check for duplicates
      indices_to_remove = []
      existing_workloads = {}
      for index, workload in enumerate(workload_list):
          if workload['name'] in existing_workloads:
              if existing_workloads[workload['name']] is not None:
                  self.logging.log('info', 'duplicate runs of %s found: %s (%s) -- %s (%s)'%(workload['name'], existing_workloads[workload['name']]['dir'], existing_workloads[workload['name']]['time'], workload['emon_dir'], workload['emon_created'])) if self.VERBOSE == True else 0
                  if existing_workloads[workload['name']]['time'] > workload['emon_created']:
                      indices_to_remove.append(index)
                  elif existing_workloads[workload['name']]['time'] < workload['emon_created']:
                      indices_to_remove.append(existing_workloads[workload['name']]['index'])
                  else:
                      self.logging.log('error', 'duplicate runs of %s have the same emon creation timestamp -- arbitrarily dropping one run!'%(workload['name']))
                      indices_to_remove.append(index)
              else:
                  self.logging.log('warning', 'found duplicate run %s, but do not have emon creation timestamp -- arbitrarily dropping one run!'%(workload['name']))
                  indices_to_remove.append(index)
          else:
              if 'emon_created' in workload:
                  existing_workloads[workload['name']] = {'index': index, 'time': workload['emon_created'], 'dir': workload['emon_dir']}
              else:
                  existing_workloads[workload['name']] = None

      for index in sorted(indices_to_remove, reverse=True):  # need to remove indices in reverse order to not affect list order during deletion
          self.logging.log('warning', 'Removing duplicate run %s from cross-workload set @ index %d'%(workload_list[index]['name'], index))
          del workload_list[index]

   
      # one time thing: copy raw emon
      #if os.path.isdir(self.results_dir + "/emon") != True:
      #  subprocess.check_output("mkdir %s"%(self.results_dir + "/emon"), shell=True)
      #for entry in workload_list:
      #  if 'emon_dir' in entry:
      #    emon_dir = entry['emon_dir']

      #    possible_files = [emon_dir + '/emon.log', emon_dir + '/emon.dat', emon_dir + '/emon.txt']
      #    for file in possible_files:
      #      if os.path.isfile(file):
      #        output = self.results_dir + "/emon/" + entry['name'] + '_emon.log'
      #        subprocess.check_output("cp %s %s"%(file, output), shell=True)
      #        break

      #    possible_files = [emon_dir + '/../emonv.log', emon_dir + '/../emonv.dat', emon_dir + '/../emonv.txt',
      #                emon_dir + '/../emon-v.log', emon_dir + '/../emon-v.dat', emon_dir + '/../emon-v.txt',
      #                emon_dir + '/emonv.log', emon_dir + '/emonv.dat', emon_dir + '/emonv.txt',
      #                emon_dir + '/emon-v.log', emon_dir + '/emon-v.dat', emon_dir + '/emon-v.txt']
      #    for file in possible_files:
      #      if os.path.isfile(file):
      #        output = self.results_dir + "/emon/" + entry['name'] + '_emonv.log'
      #        subprocess.check_output("cp %s %s"%(file, output), shell=True)
      #        break

      #    possible_files = [emon_dir + '/../emonm.log', emon_dir + '/../emonm.dat', emon_dir + '/../emonm.txt',
      #                emon_dir + '/../emon-m.log', emon_dir + '/../emon-m.dat', emon_dir + '/../emon-m.txt',
      #                emon_dir + '/emonm.log', emon_dir + '/emonm.dat', emon_dir + '/emonm.txt',
      #                emon_dir + '/emon-m.log', emon_dir + '/emon-m.dat', emon_dir + '/emon-m.txt',
      #                emon_dir + '/../emonM.log', emon_dir + '/../emonM.dat', emon_dir + '/../emonM.txt',
      #                emon_dir + '/../emon-M.log', emon_dir + '/../emon-M.dat', emon_dir + '/../emon-M.txt',
      #                emon_dir + '/emonM.log', emon_dir + '/emonM.dat', emon_dir + '/emonM.txt',
      #                emon_dir + '/emon-M.log', emon_dir + '/emon-M.dat', emon_dir + '/emon-M.txt']
      #    for file in possible_files:
      #      if os.path.isfile(file):
      #        output = self.results_dir + "/emon/" + entry['name'] + '_emonM.log'
      #        subprocess.check_output("cp %s %s"%(file, output), shell=True)
      #        break

      return workload_list


  def aibench_list(self, entry):
      perf_keyphrases = ['Total words per second', 'Throughput (images/second)', 'Throughput (words/second)',
                       'Throughput (queries/second)', 'Total activity recognition fps', 'Throughput (streams/second)',
                       'Total compute infer fps', 'Total E2E detect fps', 'Throughput (samples/second)',
                       'Average Rate (images/second)', 'Total images processed per second (Throughput)']
      expanded_list = []
      existing_runs = {}
      root_dir = entry['search_dir']
      for node_dir in glob(root_dir + '/*/'):
          match_obj = re.search(r'data_collection_(.*)-(fmx\d+)', node_dir)
          if match_obj is None:
              continue
          run_timestamp = match_obj.group(1)
          node = match_obj.group(2)
          for workload_dir in glob(node_dir + '/*/'):
              workload = workload_dir.split('/')[-2]
              for config_dir in glob(workload_dir + '/*/'):
                  config = config_dir.split('/')[-2]
                  perf_type = config.split('_')[-1]
                  if 'flops' in perf_type.lower():
                      metrics = 'skx-2s-flops-only.xml'
                      agg_secs = 0.02  # 10ms => 20ms
                  elif 'memory' in perf_type.lower():
                      metrics = 'skx-2s-memory-only.xml'
                      agg_secs = 0.01  # 5ms => 10ms
                  elif 'proxy' in perf_type.lower():
                      metrics = 'skx-2s-proxy-only.xml'
                      agg_secs = 0.04  # 10ms => 40ms
                  else:
                      metrics = 'skx-2s.xml'
                      agg_secs = 3.0  # 100ms => 3sec
                  matches = re.findall(r'\d+', config)
                  instances = matches[0]
                  cores_per_instance = matches[1]
                  core_freq = str(float(matches[2]) / 1000.0)
                  uncore_freq = str(float(matches[3]) / 1000.0)
                  dram_freq = matches[4]
                  run = "%s_%si_%scpi_%scf_%suf_%sdf_%s"%(workload, instances, cores_per_instance,
                                                          core_freq, uncore_freq, dram_freq, perf_type)
                  for namespace_dir in glob(config_dir + '/*/'):
                      perf = match_obj = None
                      result_log = namespace_dir + 'result.log'
                      #TODO - need standardized perf reporting format to parse
                      if os.path.isfile(result_log):
                          fp = open(result_log, 'rt')
                          contents = fp.read()
                          fp.close()
                          for keyphrase in perf_keyphrases:
                              if keyphrase in contents:
                                  regex_phrase = keyphrase.replace(r'(', r'\(').replace(r')', r'\)').replace(r'/', r'\/')
                                  match_obj = re.search(regex_phrase + r'.*\b(\d+\.\d*)', contents)
                                  break
                      if match_obj is not None:
                          perf = match_obj.group(1)
                      else:
                          self.logging.log("warning", "%s couldn't parse performance from %s"%(run, result_log))
                      for instance_dir in glob(namespace_dir + '/*/'):
                          last_level_instance_dir = instance_dir.split('/')[-2]
                          if perf_type.lower() in last_level_instance_dir.lower():
                              for perf_dir in glob(instance_dir + '/*/'):
                                  for emon_dir in glob(perf_dir + '/*/'):
                                      emon_file = emon_dir + 'emon.log'
                                      if not os.path.isfile(emon_file):
                                          continue
                                      emon_bytes = os.path.getsize(emon_file)
                                      last_modified = os.path.getmtime(emon_file)

                                      filter_scheme = entry['filter_scheme'] if 'filter_scheme' in entry else None
                                      filter_start = entry['filter_start'] if 'filter_start' in entry else None
                                      filter_stop = entry['filter_stop'] if 'filter_stop' in entry else None
                                      filter_percent = entry['filter_percent'] if 'filter_percent' in entry else None
                                      filter_column = entry['filter_column'] if 'filter_column' in entry else None
                                      if 'manual_filter' in entry and entry['manual_filter'] is not None:
                                          for item in entry['manual_filter']:
                                              if item['name'] in run:
                                                  self.logging.log('info', 'setting manual filter for %s'%(run))
                                                  if 'filter_start' in item:
                                                      filter_start = item['filter_start']
                                                  if 'filter_stop' in item:
                                                      filter_stop = item['filter_stop']
                                                  if 'filter_percent' in item:
                                                      filter_percent = item['filter_percent']
                                                  if 'filter_scheme' in item:
                                                      filter_scheme = item['filter_scheme']
                                                  if 'filter_column' in item:
                                                      filter_column = item['filter_column']
                                      new_entry = {
                                          'name':           run,
                                          'filter_start':   filter_start,
                                          'filter_stop':    filter_stop,
                                          'filter_percent': filter_percent,
                                          'filter_scheme':  filter_scheme,
                                          'filter_column':  filter_column,
                                          'metrics':        metrics,
                                          'perf':           perf,
                                          'agg_secs':       agg_secs,
                                          'emon_dir':       emon_dir.rstrip('/'),
                                          'node':           node,
                                          'run_timestamp':  run_timestamp,
                                          'emon_bytes':     emon_bytes,
                                          'emon_created':  last_modified,
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
                                          # there may be duplicate runs, take the most recent
                                          if run in existing_runs:
                                              self.logging.log("warning", "Removing duplicate run %s"%(run))
                                              if existing_runs[run] < last_modified:  # if existing run is older, drop it and add this run
                                                  expanded_list = [i for i in expanded_list if not (i['name'] == run)]
                                                  existing_runs[run] = last_modified
                                                  expanded_list.append(new_entry)
                                              # else existing run is more recent, drop this run
                                          else:
                                              existing_runs[run] = last_modified
                                              expanded_list.append(new_entry)
      return expanded_list


  def aibt_list(self, entry):
      expanded_list = []
      existing_runs = {}
      root_dir = entry['search_dir']
      for run_dir in glob(root_dir + '/Run*/'):
          run = run_dir.split('/')[-2]
          for workload_dir in glob(run_dir + '/*/'):
              workload = workload_dir.split('/')[-2].replace('_', '-')
              for config_dir in glob(workload_dir + '/aibt*/'):
                  config = config_dir.split('/')[-2]
                  node = config.split('-')[-1]
                  precision = config.split('-')[-3]
                  engine = config.split('-')[-4]

                  perf_type = 'default' if 'perf_type' not in entry else entry['perf_type']
                  perf = None if 'perf' not in entry else entry['perf']
                  metrics = 'clx-2s.xml' if 'metrics' not in entry else entry['metrics']
                  agg_secs = 3.5 if 'agg_secs' not in entry else entry['agg_secs']
                  instances = '56' if 'instances' not in entry else entry['instances']
                  cores_per_instance = '1' if 'cores_per_instance' not in entry else entry['cores_per_instance']
                  core_freq = 'def' if 'core_freq' not in entry else entry['core_freq']
                  uncore_freq = 'def' if 'uncore_freq' not in entry else entry['uncore_freq']
                  dram_freq = '2933' if 'dram_freq' not in entry else entry['dram_freq']

                  full_run = "%s-%s-%s-%s_%si_%scpi_%scf_%suf_%sdf_%s"%(workload, engine, precision, run,
                                                                        instances, cores_per_instance,core_freq,
                                                                        uncore_freq, dram_freq, perf_type)
                  for namespace_dir in glob(config_dir + '0/*/'):
                      for emon_dir in glob(namespace_dir + 'plugins/emon/'):
                          emon_file = emon_dir + 'emon.log'
                          if not os.path.isfile(emon_file):
                              self.logging.log("warning", "Could not find emon.log in %s"%(emon_dir))
                              continue
                          emon_bytes = os.path.getsize(emon_file)
                          last_modified = os.path.getmtime(emon_file)

                          filter_scheme = entry['filter_scheme'] if 'filter_scheme' in entry else None
                          filter_start = entry['filter_start'] if 'filter_start' in entry else None
                          filter_stop = entry['filter_stop'] if 'filter_stop' in entry else None
                          filter_percent = entry['filter_percent'] if 'filter_percent' in entry else None
                          filter_column = entry['filter_column'] if 'filter_column' in entry else None
                          if 'manual_filter' in entry and entry['manual_filter'] is not None:
                              for item in entry['manual_filter']:
                                  if item['name'] in full_run:
                                      self.logging.log('info', 'setting manual filter for %s'%(full_run))
                                      if 'filter_start' in item:
                                          filter_start = item['filter_start']
                                      if 'filter_stop' in item:
                                          filter_stop = item['filter_stop']
                                      if 'filter_percent' in item:
                                          filter_percent = item['filter_percent']
                                      if 'filter_scheme' in item:
                                          filter_scheme = item['filter_scheme']
                                      if 'filter_column' in item:
                                          filter_column = item['filter_column']
                          new_entry = {
                              'name':              full_run,
                              'filter_start':      filter_start,
                              'filter_stop':       filter_stop,
                              'filter_percent':    filter_percent,
                              'filter_scheme':     filter_scheme,
                              'filter_column':     filter_column,
                              'metrics':           metrics,
                              'perf':              perf,
                              'agg_secs':          agg_secs,
                              'emon_dir':          emon_dir.rstrip('/'),
                              'node':              node,
                              'emon_bytes':        emon_bytes,
                              'precision':   precision,
                              'engine':             engine,
                              'run_count':         run,
                              'workload_name':     workload,
                              'emon_created':     last_modified,
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

                                  if (exception is None and item in full_run) or (exception is not None and exception not in full_run and item in full_run):
                                      self.logging.log('info', 'excluding %s from workloads'%(full_run))
                                      new_entry = None
                                      break

                          if 'include' in entry and entry['include'] is not None:
                              match = False
                              for item in entry['include']:
                                  if item in full_run:
                                      match = True
                                      break
                              if match == False:
                                  self.logging.log('info', 'excluding %s from workloads'%(full_run))
                                  new_entry = None

                          if new_entry is not None:
                              # there may be duplicate runs, take the most recent
                              if full_run in existing_runs:
                                  self.logging.log("warning", "Removing duplicate run %s in %s"%(full_run, emon_dir))
                                  if existing_runs[full_run] < last_modified:  # if existing run is older, drop it and add this run
                                      expanded_list = [i for i in expanded_list if not (i['name'] == full_run)]
                                      existing_runs[full_run] = last_modified
                                      expanded_list.append(new_entry)
                                  # else existing run is more recent, drop this run                              
                              else:
                                  existing_runs[full_run] = last_modified
                                  expanded_list.append(new_entry)
      return expanded_list


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
              if 'manual_filter' in entry and entry['manual_filter'] is not None:
                  for item in entry['manual_filter']:
                      if item['name'] in run:
                          #self.logging.log('info', 'setting manual filter for %s'%(run))
                          if 'filter_start' in item:
                              filter_start = item['filter_start']
                          if 'filter_stop' in item:
                              filter_stop = item['filter_stop']
                          if 'filter_percent' in item:
                              filter_percent = item['filter_percent']
                          if 'filter_scheme' in item:
                              filter_scheme = item['filter_scheme']
                          if 'filter_column' in item:
                              filter_column = item['filter_column']

              if file == 'emon.dat':
                  new_entry = {
                      'name':           name,
                      'filter_start':   filter_start,
                      'filter_stop':    filter_stop,
                      'filter_percent': filter_percent,
                      'filter_scheme':  filter_scheme,
                      'filter_column':  filter_column,
                      'start':          None,
                      'stop':           None,
                      'metrics':        metrics,
                      'perf':           None,
                      'agg_secs':       3.0,
                      'emon_dir':       root,
                      'node':           None,
                      'timestamp':      None,
                      'emon_bytes':     os.path.getsize(file_path),
                      'emon_created':   os.path.getmtime(file_path),
                  }

              elif '.xlsx' in file:
                  include_file = file_path.replace(".xlsx", ".include")
                  exclude_file = file_path.replace(".xlsx", ".exclude")
                  if not os.path.isfile(include_file) and not os.path.isfile(exclude_file):
                      xl = pd.ExcelFile(file_path)
                      if 'emonV' not in xl.sheet_names or 'system view' not in xl.sheet_names:
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


  def kafka_emulator_list(self, entry):
      expanded_list = []
      existing_runs = {}
      #  open summary file to get namespaces
      csv = pd.read_csv(entry['summary_file'], index_col=0)

      #  navigate each namespace directory structure
      root_dir = entry['search_dir']
      path_columns = ['BROKER_CORES', 'BROKERS', 'STORAGE_MEDIUM', 'STORAGE_DEVICES', 'PRODUCERS', 'CONSUMERS', 'ITEMS_PER_ELEMENT', 'PRODUCER_BATCH_SIZE', 'PRODUCER_LINGER_MS', 'CONSUMER_FMB', 'CONSUMER_FMWM', 'ITEM_SIZE', 'ELEMENT_COUNT', 'SPEED']
      for index, row in csv.iterrows():
          dir = root_dir
          namespace = row['STORAGE_MEDIUM']
          for column in path_columns:
              dir += '/' + column + '#' + str(row[column])
          dir += '/' + namespace

          for dummy_dir in glob(dir + '/dummy*/'):
              broker_num = dummy_dir.split('/')[-2].replace('dummy-e2e-kafkabroker-', '').split('-')[0]
              for perf_dir in glob(dummy_dir + '/perf*/'):
                  for emon_dir in glob(perf_dir + '/emon*/'):
                      emon_file = emon_dir + 'emon.log'
                      if os.path.isfile(emon_file):
                          run = 'KafkaEmulation-' + namespace + '-NumBrokers' + str(row['BROKERS']) + '-Size' + str(row['ITEM_SIZE']) + '-Broker' + str(broker_num) + '_1i_112cpi_defcf_defuf_2666df_default'

                          filter_scheme = entry['filter_scheme'] if 'filter_scheme' in entry else None
                          filter_start = entry['filter_start'] if 'filter_start' in entry else None
                          filter_stop = entry['filter_stop'] if 'filter_stop' in entry else None
                          filter_percent = entry['filter_percent'] if 'filter_percent' in entry else None
                          filter_column = entry['filter_column'] if 'filter_column' in entry else None
                          if 'manual_filter' in entry and entry['manual_filter'] is not None:
                              for item in entry['manual_filter']:
                                  if item['name'] in run:
                                      self.logging.log('info', 'setting manual filter for %s'%(run))
                                      if 'filter_start' in item:
                                          filter_start = item['filter_start']
                                      if 'filter_stop' in item:
                                          filter_stop = item['filter_stop']
                                      if 'filter_percent' in item:
                                          filter_percent = item['filter_percent']
                                      if 'filter_column' in item:
                                          filter_column = item['filter_column']
                                      if 'filter_scheme' in item:
                                          filter_scheme = item['filter_scheme']

                          new_entry = {
                              'name':           run,
                              'filter_start':   filter_start,
                              'filter_stop':    filter_stop,
                              'filter_percent': filter_percent,
                              'filter_scheme':  filter_scheme,
                              'filter_column':  filter_column,
                              'metrics':        'skx-2s.xml',
                              'perf':           row['produceToConsume average'],
                              'agg_secs':       entry['agg_secs'],
                              'emon_dir':       emon_dir.rstrip('/'),
                              'emon_bytes':     os.path.getsize(emon_file),
                              'emon_created':   os.path.getmtime(emon_file),
                          }
                          # add items from summary csv
                          for key,val in row.iteritems():
                              new_entry[key] = val
                          # add items from yaml entry
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


  def aibt_argo_list(self, entry):
      expanded_list = []
      existing_runs = {}
      root_dir = entry['search_dir']
      for run_dir in glob(root_dir + '/iter*/'):
          run = 'Run' + re.findall(r'\d+', run_dir.split('/')[-2])[0]
          for workload_dir in glob(run_dir + '/*/'):
              workload = workload_dir.split('/')[-2].replace('_', '-')
              for config_dir in glob(workload_dir + '/*aibt-emon*/'):
                  emon_dir = config_dir
                  config = config_dir.split('/')[-2]
                  timestamp = config.split('_')[0] + '_' + config.split('_')[1]
                  node = None
                  cpu = config.split('_')[-1]
                  engine = config.split('_')[-2]
                  precision = config.split('_')[-3]
                  batch = re.findall(r'\d+', config.split('_')[-4])[0]
                  cores_per_instance = re.findall(r'\d+', config.split('_')[-5])[0]
                  instances = re.findall(r'\d+', config.split('_')[-6])[0]

                  perf_type = 'default' if 'perf_type' not in entry else entry['perf_type']
                  perf = None if 'perf' not in entry else entry['perf']
                  metrics = 'clx-2s.xml' if 'metrics' not in entry else entry['metrics']
                  agg_secs = 3.5 if 'agg_secs' not in entry else entry['agg_secs']
                  #instances = '56' if 'instances' not in entry else entry['instances']
                  #cores_per_instance = '1' if 'cores_per_instance' not in entry else entry['cores_per_instance']
                  core_freq = 'def' if 'core_freq' not in entry else entry['core_freq']
                  uncore_freq = 'def' if 'uncore_freq' not in entry else entry['uncore_freq']
                  dram_freq = '2933' if 'dram_freq' not in entry else entry['dram_freq']

                  full_run = "%s-%s-%s-%s-%s_%si_%scpi_%scf_%suf_%sdf_%s"%(workload, engine, precision, batch, run,
                                                                        instances, cores_per_instance, core_freq,
                                                                        uncore_freq, dram_freq, perf_type)
                  emon_file = emon_dir + 'emon.log'
                  if not os.path.isfile(emon_file):
                      self.logging.log("warning", "Could not find emon.log in %s"%(emon_dir))
                      continue
                  emon_bytes = os.path.getsize(emon_file)
                  last_modified = os.path.getmtime(emon_file)

                  filter_scheme = entry['filter_scheme'] if 'filter_scheme' in entry else None
                  filter_start = entry['filter_start'] if 'filter_start' in entry else None
                  filter_stop = entry['filter_stop'] if 'filter_stop' in entry else None
                  filter_percent = entry['filter_percent'] if 'filter_percent' in entry else None
                  filter_column = entry['filter_column'] if 'filter_column' in entry else None
                  if 'manual_filter' in entry and entry['manual_filter'] is not None:
                      for item in entry['manual_filter']:
                          if item['name'] in full_run:
                              self.logging.log('info', 'setting manual filter for %s'%(full_run))
                              if 'filter_start' in item:
                                  filter_start = item['filter_start']
                              if 'filter_stop' in item:
                                  filter_stop = item['filter_stop']
                              if 'filter_percent' in item:
                                  filter_percent = item['filter_percent']
                              if 'filter_scheme' in item:
                                  filter_scheme = item['filter_scheme']
                              if 'filter_column' in item:
                                  filter_column = item['filter_column']
                  new_entry = {
                      'name':           full_run,
                      'filter_start':   filter_start,
                      'filter_stop':    filter_stop,
                      'filter_percent': filter_percent,
                      'filter_scheme':  filter_scheme,
                      'filter_column':  filter_column,
                      'metrics':        metrics,
                      'perf':           perf,
                      'agg_secs':       agg_secs,
                      'emon_dir':       emon_dir.rstrip('/'),
                      'node':           node,
                      'emon_bytes':     emon_bytes,
                      'precision':      precision,
                      'engine':         engine,
                      'batch':          batch,
                      'run_count':      run,
                      'workload_name':  workload,
                      'emon_created':   last_modified,
                  }

                  for key,val in entry.items():
                    if key != 'filter_scheme' and type(val) is not dict and type(val) is not list:  # don't need to add these
                      new_entry[key] = val

                  if 'exclude' in entry and entry['exclude'] is not None:
                      for item in entry['exclude']:
                          exception = None
                          if isinstance(item, dict):
                              exception = item['exception'] if 'exception' in item else None
                              item = item['match'] if 'match' in item else None

                          if (exception is None and item in full_run) or (exception is not None and exception not in full_run and item in full_run):
                              self.logging.log('info', 'excluding %s from workloads'%(full_run))
                              new_entry = None
                              break

                  if 'include' in entry and entry['include'] is not None:
                      match = False
                      for item in entry['include']:
                          if item in full_run:
                              match = True
                              break
                      if match == False:
                          self.logging.log('info', 'excluding %s from workloads'%(full_run))
                          new_entry = None

                  if new_entry is not None:
                      # there may be duplicate runs, take the most recent
                      if full_run in existing_runs:
                          self.logging.log("warning", "Removing duplicate run %s in %s"%(full_run, emon_dir))
                          if existing_runs[full_run] < last_modified:  # if existing run is older, drop it and add this run
                              expanded_list = [i for i in expanded_list if not (i['name'] == full_run)]
                              existing_runs[full_run] = last_modified
                              expanded_list.append(new_entry)
                          # else existing run is more recent, drop this run                              
                      else:
                          existing_runs[full_run] = last_modified
                          expanded_list.append(new_entry)
      return expanded_list


  def create_workload_list(self, entry):
    expanded_list = []
    if 'emon_dir' in entry or 'edp_file' in entry:
      expanded_list.append(entry)
    elif entry['type'] == 'aibench':
      expanded_list = self.aibench_list(entry)
    elif entry['type'] == 'aibt':
      expanded_list = self.aibt_list(entry)
    elif entry['type'] == 'edp':
      expanded_list = self.edp_list(entry)
    elif entry['type'] in ['kafka-emulator', 'kafka_emulator']:
      expanded_list = self.kafka_emulator_list(entry)
    elif entry['type'] in ['aibt-argo', 'aibt_argo']:
      expanded_list = self.aibt_argo_list(entry)
    else:
      self.logging.log('error', 'Unexpected search type %s'%(entry['type']))
    
    sorted_list = sorted(expanded_list, key = lambda x: x['emon_bytes'])
    return sorted_list

