#!/usr/bin/env python
#coding=utf8

import pexpect,sys,os,time

def nrun():
  n=20
  for i in range(n):
    print '{}/{}'.format(i,n)
    sys.stdout.flush()
    exp = pexpect.spawn('../mcgdb main')
    exp.expect('(gdb)')
    time.sleep(1)
    exp.sendline('q')
    exp.close()
    if not exp.exitstatus:
      print ('FAIL',exp.exitstatus, exp.signalstatus)
    os.system('killall -9 mcgdb_mc')
  print ''


if __name__=="__main__":
  nrun()