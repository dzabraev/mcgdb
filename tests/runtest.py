#!/usr/bin/env python
#coding=utf8

import pexpect, subprocess, time, os, socket
import atexit

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

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class ExecutableNotFound(Exception):
  def __init__(self,name):
    self.name=name
  def __str__(self,name):
    return 'cant find program `{name}` in PATH'.format(name=name)

def which(name):
    for path in os.getenv("PATH").split(os.path.pathsep):
        full_path = path + os.sep + name
        if os.path.exists(full_path):
          return full_path
    raise ExecutableNotFound(name)

class Display(object):
  __metaclass__ = Singleton
  @cleanup__init__
  def __init__(self,DISPLAY=':99',port=5906):
    self.DISPLAY=DISPLAY
    FNULL = open(os.devnull, 'w')
    self.xvfb   = subprocess.Popen(['Xvfb',DISPLAY], stdout=FNULL, stderr=subprocess.STDOUT)
    self.x11vnc = subprocess.Popen(['x11vnc', '-display', DISPLAY, '-rfbport', str(port)], stdout=FNULL, stderr=subprocess.STDOUT)
    print 'VIEW DISPLAY: `vncviewer localhost:{port}`'.format(port=port)

  @cleanup__close__
  def close(self):
    self.x11vnc.kill()
    self.xvfb.kill()



class McgdbWin(object):

  ButtonPress = 0
  ButtonRelease = -1

  @cleanup__init__
  def __init__(self,cmd):
    ENV={
      'DISPLAY':Display().DISPLAY,
    }
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    iostub = os.path.abspath('iostub.py')
    python = which('python')
    xterm=which('xterm')
    args=[xterm,'-geometry','+0+0','-e',' '.join([python,iostub, str(port), cmd])+'; sleep 999']
    print args
    self.xterm = subprocess.Popen(args,env=ENV)
    sock.listen(1)
    conn, addr = sock.accept()
    print '{cmd} started'.format(cmd=cmd)
    self.conn = conn
    atexit.register(self.close)

  def mouse_click_msg(self,row,col):
    pat = lambda end : '{ESC}[{button};{row};{col}{end}'.format(
      ESC=chr(27),
      button='<0',
      col=col,
      row=row,
      end=end,
    )
    return pat('M')+pat('m')

  def click(self,row,col):
    msg=self.mouse_click_msg(row,col)
    print msg
    self.conn.sendall(self.mouse_click_msg(row=row,col=col))

  @cleanup__close__
  def close(self):
    self.xterm.kill()

class Gdb(object):
  @cleanup__init__
  def __init__(self,args='',env={}):
    ENV={
      'WIN_LIST':'',
    }
    ENV.update(env)
    self.gdb = pexpect.spawn('../mcgdb {args}'.format(args=args),env=ENV)
    atexit.register(self.close)
    self.closed=False

  def open_window(self,win_name):
    self.gdb.sendline('mcgdb open {win_name} --manually'.format(win_name=win_name))
    self.gdb.expect('Execute manually `(/.+/mcgdb_mc -e --gdb-port=\d+)` for start window')
    exec_cmd = self.gdb.match.groups()[0]
    return McgdbWin(exec_cmd)

  @cleanup__close__
  def close(self):
    self.gdb.kill(9)


def runtest():
  gdb=Gdb('main')
  aux=gdb.open_window('aux')
  time.sleep(0xfffffff)

if __name__ == "__main__":
  runtest()
