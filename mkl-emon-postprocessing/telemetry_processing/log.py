import os
import multiprocessing

class Log:
  def __init__(self):
    manager = multiprocessing.Manager()
    self.transcript = manager.list()
    self.errors = manager.list()
    self.warnings = manager.list()

  def log(self, level, message):
    id = os.getpid()
    self.transcript.append(message)

    if "warning" in level.lower():
        self.warnings.append(message)
        print("[WARN][%d]\t"%(id), message)
    elif "error" in level.lower():
        self.errors.append(message)
        print("[ERROR][%d]\t"%(id), message)
    else:
        print("[INFO][%d]\t"%(id), message)

  def get_errors(self):
    return self.errors

  def get_warnings(self):
    return self.warnings

  def get_transcript(self):
    return self.transcript

