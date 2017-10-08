#!/usr/bin/env python
#coding=utf8

import compare,os,subprocess

LOGFILE='wait_change_bug_1.log'

def runtest(delay=0.3):
  cmd="unxz --keep --force wait_change_bug_1.play.xz"
  print cmd
  subprocess.check_call(cmd, shell=True)
  cmd="mcgdb_play.py wait_change_bug_1.py --delay={delay} --output=record.new.play".format(delay=delay)
  print cmd
  subprocess.check_call(cmd, shell=True)
  with open(LOGFILE,'wb') as logfile:
    res=compare.compare(
      journal1='wait_change_bug_1.play',
      journal2='record.new.play',
      colorize=False,
      output=logfile,
      regexes='../variables/regexes.py',
    )
  return res,'See %s' % os.path.join(os.getcwd(),LOGFILE)
