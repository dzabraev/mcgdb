#!/usr/bin/env python
#coding=utf8

import pty,sys,os,select,socket,fcntl,termios,time,errno,signal


def do_child(executable,args):
  os.execv(executable,args)

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


def do_parent(port,child_fd,child_pid):
  sock = socket.socket()
  sock.connect(('localhost',port))
  stdin_fd = sys.stdin.fileno()
  stdout_fd = sys.stdout.fileno()
  sock_fd = sock.fileno()
  pair={
    stdin_fd : child_fd,
    child_fd : stdout_fd,
    sock_fd  : child_fd,
  }
  SigHandler(signal.SIGWINCH,lambda signo,frame : handler_sigwich(signo,frame,stdin_fd=stdin_fd,child_fd=child_fd,child_pid=child_pid) )
  #signal.signal(signal.SIGWINCH,lambda signo,frame : handler_sigwich(signo,frame,stdin_fd=stdin_fd,child_fd=child_fd,child_pid=child_pid))
  rlist = pair.keys()
  do_nonblock = lambda fd : fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)
  map(do_nonblock,rlist)
  select.select([child_fd],[],[]) #wait first child output and then change terminal settings
  termios.tcsetattr(stdout_fd, termios.TCSANOW, termios.tcgetattr(child_fd))
  log=open('/tmp/mclog.log','w')
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
        os.write(pair[rfd],res)
        if rfd==child_fd:
          sock.sendall(res)
        elif rfd==stdin_fd:
          log.write(res)
          log.flush()

def stub():
  port = int(sys.argv[1])
  executable = sys.argv[2]
  args = sys.argv[2:]
  pid,fd = pty.fork()
  if pid==0:
    do_child(executable,args)
  else:
    CHILD_PID = pid
    do_parent(port=port,child_fd=fd,child_pid=pid)


if __name__ == "__main__":
  stub()