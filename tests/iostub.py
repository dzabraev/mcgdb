#!/usr/bin/env python
#coding=utf8

import pty,sys,os,select,socket,fcntl,termios,time,errno,signal,argparse,json,struct


def do_child(executable,args):
  os.execv(executable,[executable] + args)

def copy_termsize(from_fd,to_fd):
  fcntl.ioctl(to_fd, termios.TIOCSWINSZ,
    fcntl.ioctl(from_fd, termios.TIOCGWINSZ, '\0'*8))

#def handler_sigwich(signo,frame,stdin_fd,child_fd,child_pid):
#  fcntl.ioctl(child_fd, termios.TIOCSWINSZ,
#    fcntl.ioctl(stdin_fd, termios.TIOCGWINSZ, '\0'*8))

class SigHandler(object):
  def __init__(self,sig,cb):
    self.cb = cb
    self.saved = signal.signal(sig,self.handler)
  def handler(self,signo,frame):
    self.cb(signo,frame)
    if self.saved:
      self.saved(signo,frame)

class StreamJson(object):
  def __init__(self):
    self.cbs = []

  def add_cb(self,cb):
    self.cbs.append(cb)

  def __call__(self,data):
    return self.retranslate_stream(data)

  def retranslate(self,data):
    ddata = json.dumps(data)+'\n'
    for cb in self.cbs:
      cb(ddata)

  def retranslate_stream(self,data):
    self.retranslate({'stream':data})

  def retranslate_sigwinch(self):
    data=fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, '\0'*8)
    s=struct.unpack('HHHH',data)
    d={'sig':signal.SIGWINCH,'col':s[1],'row':s[0]}
    self.retranslate(d)

def do_nonblock(fd):
  fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)

def is_process_alive(pid):
  try:
    os.kill(pid,0)
  except OSError:
    return False
  else:
    return True

def do_parent(child_fd,child_pid,pport,xport,pfname,xfname):
  ''' This program grabs terminal output from child program (child_fd) and retranslate to pfname and/or pport.
      Simmetrically, program grabs input (stdit_fd) -- byte stream from x-window and retranslate
      input to xport and xfname.

      pfname and xfname be filenames
      xport and pport be port numbers. You should bind-listen-accept this ports.

      xport,pport,xfname,pfname may be None

      Apart from io recording this program record and retranslate to child program following signals: SIGWINCH
  '''
  stdin_fd = sys.stdin.fileno()
  stdout_fd = sys.stdout.fileno()
  do_nonblock(stdin_fd)
  do_nonblock(child_fd)
  stream_from_term = StreamJson()
  child_file = os.fdopen(child_fd,'wb', 0)
  sys.stdout = os.fdopen(sys.stdout.fileno(), 'wb', 0)
  retranslate={
    stdin_fd : [lambda data : child_file.write(data), stream_from_term],
    child_fd : [lambda data : sys.stdout.write(data)],
  }
  rlist=[child_fd,stdin_fd]
  if pport is not None:
    psock = socket.socket()
    psock.connect(('localhost',pport))
    retranslate[child_fd].append(lambda data : psock.sendall(data))
  if pfname is not None:
    pfile = open(pfname,'wb')
    retranslate[child_fd].append(lambda data : pfile.write(data))
  if xport is not None:
    xsock = socket.socket()
    xsock.connect(('localhost',xport))
    stream_from_term.add_cb(lambda data : xsock.sendall(data))
  if xfname is not None:
    xfile = open(xfname,'wb')
    stream_from_term.add_cb(lambda data : xfile.write(data))
  SigHandler(signal.SIGWINCH,lambda signo,frame : stream_from_term.retranslate_sigwinch())
  SigHandler(signal.SIGWINCH,lambda signo,frame : copy_termsize(from_fd=stdin_fd,to_fd=child_fd))
  select.select([child_fd],[],[]) #wait first child output and then change terminal settings
  termios.tcsetattr(stdout_fd, termios.TCSANOW, termios.tcgetattr(child_fd))
  copy_termsize(from_fd=stdin_fd,to_fd=child_fd)
  while True:
    try:
      ready_fds = select.select(rlist,[],[])
    except select.error as e:
      if e[0]==errno.EINTR:
        continue
      else:
        exc_info = sys.exc_info()
        raise exc_info[0], exc_info[1], exc_info[2]
    ready_read_fds = ready_fds[0]
    for rfd in ready_read_fds:
      while True:
        try:
          res = os.read(rfd,1024)
        except OSError as e:
          if e.errno==errno.EAGAIN:
            break
          elif e.errno==errno.EIO:
            termios.tcsetattr(stdout_fd, termios.TCSANOW, termios.tcgetattr(child_fd))
            sys.exit(0)
          else:
            exc_info = sys.exc_info()
            raise exc_info[0], exc_info[1], exc_info[2]
        for cb in retranslate[rfd]:
          cb(res)

def stub():
  parser = argparse.ArgumentParser()
  parser.add_argument("--pport", help="connect to port and retranslate ewerything from program to port", type=int)
  parser.add_argument("--xport", help="connect to port and retranslate ewerything from xwin to port", type=int)

  parser.add_argument("--pfname", help="same as --pport but redirect to file", type=str)
  parser.add_argument("--xfname", help="same as --xport but redirect to file", type=str)

  parser.add_argument("--executable", help="path to prog to execute")
  parser.add_argument("--args", nargs='+',help="path to prog to execute",default=[])
  args = parser.parse_args()

  pid,fd = pty.fork()
  if pid==0:
    do_child(args.executable,args.args)
  else:
    CHILD_PID = pid
    do_parent(child_fd=fd,child_pid=pid, pport=args.pport, xport=args.xport, pfname=args.pfname, xfname=args.xfname)


if __name__ == "__main__":
  stub()