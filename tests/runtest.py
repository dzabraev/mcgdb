#!/usr/bin/env python
#coding=utf8

import pexpect, subprocess, time, os

class Display(object):
  def __init__(self,DISPLAY=':99',port=5906):
    self.DISPLAY=DISPLAY
    FNULL = open(os.devnull, 'w')
    self.xvfb   = subprocess.Popen(['Xvfb',DISPLAY], stdout=FNULL, stderr=subprocess.STDOUT)
    self.x11vnc = subprocess.Popen(['x11vnc', '-display', DISPLAY, '-rfbport', str(port)], stdout=FNULL, stderr=subprocess.STDOUT)
    print 'VIEW DISPLAY: `vncviewer localhost:{port}`'.format(port=port)

  def __exit__(self, type, value, traceback):
    print 'CALLED'
    self.x11vnc.kill()
    self.xvfb.kill()



class McgdbWin(object):
  def __init__(self,cmd):
    ENV={
      'DISPLAY':DISPLAY.DISPLAY,
    }
    args=['xterm','-geometry','+0+0','-e',cmd]
    self.xterm = subprocess.Popen(args,env=ENV)

  def __exit__(self):
    self.xterm.kill()

class Gdb(object):
  def __init__(self,args,env={}):
    ENV={
      'WIN_LIST':'',
    }
    ENV.update(env)
    self.gdb = pexpect.spawn('../mcgdb {args}'.format(args=args),env=ENV)

  def open_window(self,win_name):
    self.gdb.sendline('mcgdb open {win_name} --manually'.format(win_name=win_name))
    self.gdb.expect('Execute manually `(/.+/mcgdb_mc -e --gdb-port=\d+)` for start window')
    exec_cmd = self.gdb.match.groups()[0]
    return McgdbWin(exec_cmd)

  def __exit__(self):
    self.gdb.kill(9)


def runtest():
  global DISPLAY
  DISPLAY=Display()
  gdb=Gdb('main')
  aux=gdb.open_window('aux')
  #time.sleep(0xfffffff)

if __name__ == "__main__":
  runtest()
