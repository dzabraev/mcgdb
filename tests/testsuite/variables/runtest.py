#!/usr/bin/env python
#coding=utf8

import compare,os,subprocess

LOGFILE='variables.log'

def runtest(delay=0.1):
  cmd="unxz --keep --force record.play.xz"
  print cmd
  subprocess.check_call(cmd, shell=True)
  cmd="mcgdb_play.py record.py --delay={delay} --output=record.new.play".format(delay=delay)
  print cmd
  subprocess.check_call(cmd, shell=True)
  with open(LOGFILE,'wb') as logfile:
    res=compare.compare(
      journal1='record.play',
      journal2='record.new.play',
      colorize=False,
      output=logfile,
      regexes='regexes.py',
    )
  return res,'See %s' % os.path.join(os.getcwd(),LOGFILE)
