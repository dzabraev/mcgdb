#!/usr/bin/env python
#coding=utf8
import pexpect,os,socket,subprocess,json,signal
import pexpect.fdpexpect

import distutils.spawn
which = distutils.spawn.find_executable

from common import Gdb,FNULL

def open_sock():
  sock = socket.socket()
  sock.bind(('localhost',0))
  sock.listen(1)
  return sock, sock.getsockname()[1]

XTERM=which('xterm')
PYTHON=which('python')
IOSTUB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'iostub.py')
GDB=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'mcgdb')


def split_first(s,ch='\n'):
  spl=s.split(ch)
  return spl[0], ch.join(spl[1:])

class XtermGdb(Gdb):
  def spawn(self):
    xsock,xport = open_sock()
    psock,pport = open_sock()
    cmd='{XTERM} -e "{PYTHON} {IOSTUB} --executable={GDB} --xport={XPORT} --pport={PPORT}; sleep 999"'.format(
      XTERM=XTERM,
      PYTHON=PYTHON,
      IOSTUB=IOSTUB,
      GDB=GDB,
      XPORT=xport,
      PPORT=pport,
    )
    print cmd
    self.proc = subprocess.Popen(cmd,shell=True,stdout=FNULL,stderr=FNULL)
    pconn = psock.accept()[0]
    xconn = xsock.accept()[0]
    self.gdb = pexpect.fdpexpect.fdspawn(pconn.fileno())
    self.xconn = xconn
    self.pconn = pconn
    self.saved=''

  def kill(self):
    os.kill(self.proc.pid,signal.SIGTERM)
    os.system('killall -9 gdb')

  def get_token(self):
    data=''
    while True:
      b=self.xconn.recv(1)
      if b=='\n':
        return json.loads(data)
      data+=b

  def get_action(self):
    while True:
      if '\n' in self.saved:
        s1,self.saved = split_first(self.saved)
        if len(s1)>0:
          return {'command':s1}
        else:
          continue
      token=self.get_token()
      if 'stream' in token:
        stream = token['stream']
        if '\n' in stream:
          s1,self.saved = split_first(stream)
          res = self.saved + s1
          if len(res)==0:
            continue
          return {'command':res}
        else:
          self.saved+=stream
      if 'sig' in token:
        return token

def main():
  gdb=XtermGdb()
  while True:
    print gdb.get_action()


if __name__ == "__main__":
  main()