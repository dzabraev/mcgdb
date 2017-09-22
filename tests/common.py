#!/usr/bin/env python
#coding=utf8

import pexpect, subprocess, time, os, socket, sys, re, select, pty
import atexit
import pyte

FNULL = open(os.devnull, 'w')

def cleanup__init__(func):
  def decorated(self,*args,**kwargs):
    atexit.register(self.close)
    self.closed=False
    return func(self,*args,**kwargs)
  return decorated

def cleanup__close__(func):
  def decorated(self,*args,**kwargs):
    if self.closed:
      return
    res = func(self,*args,**kwargs)
    self.closed=True
    return res
  return decorated

class McgdbWin(object):
  def __init__(self,cmd,cols=80,lines=24):
    self.cols=cols
    self.lines=lines
    self.screen = pyte.Screen(cols, lines)
    self.stream = pyte.Stream(self.screen)
    self.stream.use_utf8=False
    self.p_pid, self.master_fd = pty.fork()
    if self.p_pid == 0: #Child
      args=cmd.split()
      efile=args[0]
      os.execve(efile,args,dict(TERM="xterm", COLUMNS=str(cols), LINES=str(lines)))
    else:
      print self.p_pid
      print cmd

  def feeding(self,timeout=5):
    t0=time.time()
    while True:
      d = timeout - (time.time() - t0)
      if d<0:
        return
      rready,_wready,_xready = select.select([self.master_fd],[],[],d)
      if rready==[]:
        return
      data=os.read(self.master_fd,1024)
      self.stream.feed(data)

class Gdb(object):
  @cleanup__init__
  def __init__(self,args='',env={}):
    self.ENV={
      'WIN_LIST':'',
    }
    self.ENV.update(env)
    self.exec_args=args
    self.spawn()
    atexit.register(self.close)
    self.closed=False

  def spawn(self):
    self.program = pexpect.spawn('../mcgdb {args}'.format(args=self.exec_args),env=self.ENV)

  def open_window_cmd(self,win_name):
    self.program.sendline('mcgdb open {win_name} --manually'.format(win_name=win_name))
    self.program.expect('Execute manually `(/.+/mcgdb_mc -e --gdb-port=\d+)` for start window')
    exec_cmd = self.program.match.groups()[0]
    return exec_cmd

  def open_aux_win(self):
    return McgdbWin(self.open_window_cmd('aux'))

  def kill(self):
    if hasattr(self,'program'):
      self.program.kill(9)

  @cleanup__close__
  def close(self):
    self.kill()



def runtest():
  gdb=Gdb('main')
  aux=gdb.open_aux_win()
  gdb.gdb.sendline('break main')
  gdb.gdb.sendline('run')

  try:
    print "\x1b[?47h" #alternate screen
    while True:
      print '\x1b[1;1H'
      aux.feeding(timeout=0.1)
      for line in aux.screen.display:
        print line
  except:
    print "\x1b[?47l" #normal screen
    raise


if __name__ == "__main__":
  runtest()

