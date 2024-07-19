import log
import time
import pandas as pd
from datetime import datetime
from dateutil import parser


def filter(self, entry, df):
  # descriptions of schemes below
  valid_schemes = ['percent', 'interval', 'timestamp', 'seconds', 'auto']
  scheme = 'auto'  # default
  start_confidence = stop_confidence = 'manual'  # default

  if 'filter_scheme' in entry and entry['filter_scheme'] is not None:
    if entry['filter_scheme'] in valid_schemes:
      scheme = entry['filter_scheme']
    else:
      self.logging.log('error', 'Filter scheme for %s: expected %s, got %s'%(entry['name'], str(valid_schemes), entry['filter_scheme']))


  # user can specify a percent to remove from the beginning and end of workload (e.g. 10% removes first and last 10%)
  if scheme == 'percent':
    filter_percent = 10  # default

    if 'filter_percent' in entry and entry['filter_percent'] is not None:
      if isinstance(entry['filter_percent'], int) and 0 <= entry['filter_percent'] < 50:
        filter_percent = entry['filter_percent']
      else:
        self.logging.log('error', 'Filter scheme %s for %s: expected integer (0 - 49) for filter_percent, got %s (%s)'%(scheme, entry['name'], entry['filter_percent'], type(entry['filter_percent'])))

    self.logging.log('info', 'Filter scheme for %s: ignoring first and last %d%% of workload'%(entry['name'], filter_percent))
    start = int(df['interval'].max() * (filter_percent / 100.0))
    stop  = int(df['interval'].max() * ((100 - filter_percent) / 100.0))


  # user can specify start & stop intervals for a given workload
  # note that these are post-aggregation interval numbers
  elif scheme == 'interval':
    start = 0  # default
    stop = df['interval'].max()  # default

    if 'filter_start' in entry and entry['filter_start'] is not None:
      if isinstance(entry['filter_start'], int) and 0 <= entry['filter_start'] < df['interval'].max():
        start = entry['filter_start']
      else:
        self.logging.log('error', 'Filter scheme %s for %s: expected integer (0 - %d) for filter_start, got %s (%s)'%(scheme, entry['name'], df['interval'].max()-1, entry['filter_start'], type(entry['filter_start'])))

    if 'filter_stop' in entry and entry['filter_stop'] is not None:
      if isinstance(entry['filter_stop'], int) and start < entry['filter_stop'] <= df['interval'].max():
        stop = entry['filter_stop']
      else:
        self.logging.log('error', 'Filter scheme %s for %s: expected integer (%d - %d) for filter_stop, got %s (%s)'%(scheme, entry['name'], start+1, df['interval'].max(), entry['filter_stop'], type(entry['filter_stop'])))


  # user can specify start & stop relative time in seconds for a given workload
  elif scheme == 'seconds':
    start = 0  # default
    stop = df['cum_duration'].max()  # default
    
    if 'filter_start' in entry and entry['filter_start'] is not None:
      if isinstance(entry['filter_start'], int) and 0 <= entry['filter_start'] < df['cum_duration'].max():
        start = entry['filter_start']
      else:
        self.logging.log('error', 'Filter scheme %s for %s: expected integer (0 - %d) for filter_start, got %s (%s)'%(scheme, entry['name'], df['cum_duration'].max()-1, entry['filter_start'], type(entry['filter_start'])))
 
    if 'filter_stop' in entry and entry['filter_stop'] is not None:
      if isinstance(entry['filter_stop'], int) and start < entry['filter_stop'] <= df['cum_duration'].max():
        stop = entry['filter_stop']
      else:
        self.logging.log('error', 'Filter scheme %s for %s: expected integer (%d - %d) for filter_stop, got %s (%s)'%(scheme, entry['name'], start+1, df['interval'].max(), entry['filter_stop'], type(entry['filter_stop'])))

    self.logging.log('info', 'Filter scheme for %s: using seconds %d - %d'%(entry['name'], start, stop))
    start = df['cum_duration'].sub(start).abs().idxmin()
    stop = df['cum_duration'].sub(stop).abs().idxmin()


  # user can specify start & stop absolute timestamps for a given workload
  elif scheme == 'timestamp':
    start = filter_start_date = df['timestamp'].min()  # default
    stop = filter_stop_date = df['timestamp'].max()  # default

    if 'filter_start' in entry and entry['filter_start'] is not None:
      try:
        filter_start_date = parser.parse(entry['filter_start'])
      except Exception as e:
        self.logging.log('error', 'Filter scheme %s for %s: unable to parse filter_start %s as timestamp: %s'%(scheme, entry['name'], entry['filter_start'], e))

      if isinstance(filter_start_date, datetime) and start <= filter_start_date < stop:
        start = filter_start_date
      else:
        self.logging.log('error', 'Filter scheme %s for %s: expected datetime (%s - %s) for filter_start, got %s (%s)'%(scheme, entry['name'], str(start), str(stop), filter_start_date, type(filter_start_date)))

    if 'filter_stop' in entry and entry['filter_stop'] is not None:
      try:
        filter_stop_date = parser.parse(entry['filter_stop'])
      except Exception as e:
        self.logging.log('error', 'Filter scheme %s for %s: unable to parse filter_stop %s as timestamp: %s'%(scheme, entry['name'], entry['filter_stop'], e))

      if isinstance(filter_stop_date, datetime) and start < filter_stop_date <= stop:
        stop = filter_stop_date
      else:
        self.logging.log('error', 'Filter scheme %s for %s: expected datetime (%s - %s) for filter_stop, got %s (%s)'%(scheme, entry['name'], str(start), str(stop), filter_stop_date, type(filter_stop_date)))

    self.logging.log('info', 'Filter scheme for %s: using timestamps %s - %s'%(entry['name'], str(start), str(stop)))
    start = df['timestamp'].sub(start).abs().idxmin()
    stop = df['timestamp'].sub(stop).abs().idxmin()


  # breaks whole workload in chunks (windows) and compares ratio and absolute diff of averages between windows to detect start/stop
  # basically it's looking for a sharp spike followed by drop in instructions retired (or whatever column user specified)
  # works best with sharp/fast changes in behavior (idle -> 100%), but might have trouble finding start/stop with slow ramps
  elif scheme == 'auto':
    confidence_dict = {
      1: "high", 2: "high", 3: "high", 4: "high", 5: "high",
      6: "med", 7: "med", 8: "med", 9: "med", 10: "med",
      11: "low", 12: "low", 13: "low", 14: "low", 15: "low",
      16: "no",
    }
    start = int(df['interval'].max() * 0.10)  # default
    stop  = int(df['interval'].max() * 0.90)  # default
    filter_column = 'INST_RETIRED.ANY'  # default

    if df['interval'].max() < 5:
      self.logging.log('info', '%s only has %d total intervals, using default intervals %d to %d'%(entry['name'], df['interval'].max() + 1, start, stop))
      return start, start_confidence, stop, stop_confidence

    if 'filter_column' in entry and entry['filter_column'] is not None:
      if entry['filter_column'] in list(df):
        filter_column = entry['filter_column']
      else:
        self.logging.log('error', 'Filter scheme %s for %s: filter_column %s not in data'%(scheme, entry['name'], entry['filter_column'])) 

    self.logging.log('info', 'Filter scheme %s: attempting to detect workload start & stop using %s'%(entry['name'], filter_column))


    filter_window = max(0.02, (3.0 / df['interval'].max()))  # percent of total workload, start at x% and go up to y% for window size
    min_ratio = 1.5  # transitions must be at least this multiple from previous window to be considered a start or inverse of this multiple for stop
    estimated_start = estimated_stop = None
    while filter_window <= 0.15:  # start at x% and go up to y% for window size until we find answer, smaller window size = more accurate
      total_windows = min(int(1 / filter_window), df['interval'].max())
      window_width = max(df['interval'].max() * filter_window, 1.0)  # must use at least one interval
      print("%s -- %s -- %s"%(filter_window, total_windows, window_width)) if self.VERBOSE == True else 0
      last_average = None
      phase_absolutes = {}
      phase_ratios = {}

      for window_num in range(total_windows):
        window_start = int(window_num * window_width)
        window_stop = int(((window_num + 1) * window_width))
        average = df[filter_column].iloc[window_start:window_stop].mean()

        if last_average is not None and pd.isnull(last_average) == False and pd.isnull(average) == False:
          phase_absolutes[window_start] = average - last_average
          phase_ratios[window_start] = average / last_average
          print("%s:%s -- %s -- %s -- %s"%(window_start, window_stop, average, phase_ratios[window_start], phase_absolutes[window_start])) if self.VERBOSE == True else 0
        
        last_average = average

      # make sure they're not empty
      if len(phase_absolutes) > 0:
        # save first window by comparing against 2nd window (covers big spike at beginning)
        phase_absolutes[0] = phase_absolutes[int(window_width)] * -1
        phase_ratios[0] = 1.0 / phase_ratios[int(window_width)]

        # dicts of interval: average ratio diff, and interval: average absolute diff 
        # sort dicts by value and store in tuple list
        sorted_phase_ratios = sorted(phase_ratios.items(), key = lambda kv:(kv[1], kv[0]))
        sorted_phase_absolutes = sorted(phase_absolutes.items(), key = lambda kv:(kv[1], kv[0]))

        print(sorted_phase_ratios) if self.VERBOSE == True else 0
        print(sorted_phase_absolutes) if self.VERBOSE == True else 0
        print("") if self.VERBOSE == True else 0

        # compare sorted window averages
        # end of list has highest ratios & absoluates --> indicates start
        # beginning of list has lowest ratios & absoluated --> indicates stop
        # priority is given to the highest & lowest absolute values, but that interval must also appear in the top two (highest or lowest) ratios as well
        # TODO: could be used to find multiple phases, not just start/stop
        if estimated_start is None:
          if (sorted_phase_ratios[-1][0] == sorted_phase_absolutes[-1][0] and sorted_phase_ratios[-1][1] >= min_ratio) or \
             (sorted_phase_ratios[-2][0] == sorted_phase_absolutes[-1][0] and sorted_phase_ratios[-2][1] >= min_ratio):
            estimated_start = sorted_phase_absolutes[-1][0]
            start_confidence = confidence_dict[round(filter_window*100)]
            print("-----FOUND START", estimated_start) if self.VERBOSE == True else 0
          elif (sorted_phase_ratios[-1][0] == sorted_phase_absolutes[-2][0] and sorted_phase_ratios[-1][1] >= min_ratio) or \
               (sorted_phase_ratios[-2][0] == sorted_phase_absolutes[-2][0] and sorted_phase_ratios[-2][1] >= min_ratio):
            estimated_start = sorted_phase_absolutes[-2][0]
            start_confidence = confidence_dict[round(filter_window*100)]
            print("-----FOUND START", estimated_start) if self.VERBOSE == True else 0
        if estimated_stop is None:
          if (sorted_phase_ratios[0][0] == sorted_phase_absolutes[0][0] and sorted_phase_ratios[0][1] <= (1.0 / min_ratio)) or \
             (sorted_phase_ratios[1][0] == sorted_phase_absolutes[0][0] and sorted_phase_ratios[1][1] <= (1.0 / min_ratio)):
            estimated_stop = sorted_phase_absolutes[0][0]
            stop_confidence = confidence_dict[round(filter_window*100)]
            print("-----FOUND STOP", estimated_stop) if self.VERBOSE == True else 0
          elif (sorted_phase_ratios[0][0] == sorted_phase_absolutes[1][0] and sorted_phase_ratios[0][1] <= (1.0 / min_ratio)) or \
               (sorted_phase_ratios[1][0] == sorted_phase_absolutes[1][0] and sorted_phase_ratios[1][1] <= (1.0 / min_ratio)):
            estimated_stop = sorted_phase_absolutes[1][0]
            stop_confidence = confidence_dict[round(filter_window*100)]
            print("-----FOUND STOP", estimated_stop) if self.VERBOSE == True else 0

      # some error/bounds checking
      if estimated_start is not None and estimated_stop is not None:
        # can't have the stop before the start
        # stop is likely not in first 5% of run
        # start is likely not in last 5% of run
        if estimated_stop <= estimated_start or \
           estimated_stop <= (df['interval'].max() * 0.05):
          print("-----Resetting stop from", estimated_stop) if self.VERBOSE == True else 0
          estimated_stop = None

        if (estimated_stop is not None and estimated_start >= estimated_stop) or \
           estimated_start >= (df['interval'].max() * 0.95):
          print("-----Resetting start from", estimated_start) if self.VERBOSE == True else 0
          estimated_start = None

        # if we found both start & stop and they pass error checking, then exit while loop
        if estimated_start is not None and estimated_stop is not None:
          break
      
      filter_window += max(0.01, (1.0 / df['interval'].max()))


    if estimated_start is None:
      self.logging.log('warning', 'Could not auto detect start for %s'%(entry['name']))
      start_confidence = "no"
    else:
      start = estimated_start
    
    if estimated_stop is None:
      self.logging.log('warning', 'Could not auto detect stop for %s'%(entry['name']))
      stop_confidence = "no"
    else:
      stop = estimated_stop

  if stop <= start:
    self.logging.log('warning', 'Default stop is less than or equal to start for %s, reverting to end of workload'%(entry['name']))
    stop  = int(df['interval'].max())
 
  
  self.logging.log('info', 'Filter scheme for %s: using intervals %d %s confidence - %d %s confidence'%(entry['name'], start, start_confidence, stop, stop_confidence))
  return start, start_confidence, stop, stop_confidence

