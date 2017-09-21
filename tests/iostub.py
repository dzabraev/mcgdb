#!/usr/bin/env python
#coding=utf8

import pty,sys,os,select,socket,fcntl,termios,time,errno,signal,argparse


def do_child(executable,args):
  os.execv(executable,[executable] + args)

def handler_sigwich(signo,frame,stdin_fd,child_fd,child_pid):
  fcntl.ioctl(child_fd, termios.TIOCSWINSZ,
    fcntl.ioctl(stdin_fd, termios.TIOCGWINSZ, '\0'*8))

class SigHandler(object):
  def __init__(self,sig,cb):
    self.cb = cb
    self.saved = signal.signal(sig,self.handler)
  def handler(self,signo,frame):
    self.cb(signo,frame)
    if self.saved:
      self.saved(signo,frame)


def do_parent(child_fd,child_pid,pport,xport,pfname,xfname):
  stdin_fd = sys.stdin.fileno()
  stdout_fd = sys.stdout.fileno()
  xsock_fd = psock_fd = None
  xsock = psock = None
  xfile = pfile = None
  if pport is not None:
    psock = socket.socket()
    psock.connect(('localhost',pport))
    psock_fd = psock.fileno()
  if xport is not None:
    xsock = socket.socket()
    xsock.connect(('localhost',xport))
    xsock_fd = xsock.fileno()
  if pfname is not None:
    pfile = open(pfname,'wb')
    pfile
    pair[child_fd].append(.fileno())
  if xfname is not None:
    pair[stdin_fd].append(open(xfname,'wb').fileno())
  SigHandler(signal.SIGWINCH,lambda signo,frame : handler_sigwich(signo,frame,stdin_fd=stdin_fd,child_fd=child_fd,child_pid=child_pid) )
  rlist = pair.keys()
  if xsock_fd is not None:
    rlist.append(xsock_fd)
  if psock_fd is not None:
    rlist.append(psock_fd)
  do_nonblock = lambda fd : fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)
  map(do_nonblock,rlist)
  select.select([child_fd],[],[]) #wait first child output and then change terminal settings
  termios.tcsetattr(stdout_fd, termios.TCSANOW, termios.tcgetattr(child_fd))
  log=open('input.log','w')
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
          else:
            exc_info = sys.exc_info()
            raise exc_info[0], exc_info[1], exc_info[2]
        if rfd == child_fd:
          os.write(stdout_fd,res)
          if psock:
            psock.sendall(res)
          if pfname:
            
        elif rfd == stdin_fd:
          os.write(child_fd,res)
          xsock.sendall(res)

        elif rfd == psock_fd:
          
        elif rfd == xsock_fd:
          
        map(lambda fd:writeall(fd,res) pair[rfd])
        elif rfd==stdin_fd:
          log.write(res)
          log.flush()

def stub():
  parser = argparse.ArgumentParser()
  parser.add_argument("--pport", help="connect to port and retranslate ewerything from program to port", type=int)
  parser.add_argument("--xport", help="connect to port and retranslate ewerything from xwin to port", type=int)

  parser.add_argument("--pfname", help="same as --pport but redirect to file", type=str)
  parser.add_argument("--xfname", help="same as --xport but redirect to file", type=str)

  parser.add_argument("--executable", help="path to prog to execute")
  parser.add_argument("--args", nargs='+',help="path to prog to execute")
  args = parser.parse_args()

  pid,fd = pty.fork()
  if pid==0:
    do_child(args.executable,args.args)
  else:
    CHILD_PID = pid
    do_parent(child_fd=fd,child_pid=pid, pport=args.pport, xport=args.xport, pfname=args.pfname, xfname=args.xfname)


if __name__ == "__main__":
  stub()