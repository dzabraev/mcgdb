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
  def __init__(self,cmd,xterm='/usr/bin/xterm'):
    ENV={
      'DISPLAY':Display().DISPLAY,
    }
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    iostub = os.path.abspath('iostub.py')
    args=[xterm,'-geometry','+0+0','-e',' '.join([iostub, str(port), cmd])]
    print args
    self.xterm = subprocess.Popen(args,env=ENV)
    sock.listen(1)
    conn, addr = sock.accept()
    self.conn = conn
    atexit.register(self.close)

  def mouse_event_msg(self,button,col,row,end,shift=0,meta=0,ctrl=0,motion=0,wheel=0):
    return '{ESC}[{button};{col};{row}{end}'.format(
      ESC=chr(27),
      button=32 + (shift<<2) + (meta<<3) + (ctrl<<4) + (motion<<5) + (wheel<<6) + button,
      col=col,
      row=row,
      end=end
    )

  def mouse_click(self,col,row):
    self.conn.sendall(self.mouse_event_msg(self.ButtonPress,col,row,'M'))
    self.conn.sendall(self.mouse_event_msg(self.ButtonRelease,col,row,'m'))

  @cleanup__close__
  def close(self):
    self.xterm.kill()

class Gdb(object):
  @cleanup__init__
  def __init__(self,args,env={}):
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
