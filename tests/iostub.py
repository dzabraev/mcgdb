#!/usr/bin/env python
#coding=utf8

import pty,sys,os,select,socket,fcntl,termios,time,errno

def do_child(executable,args):
  os.execv(executable,args)

def do_parent(port,child_fd):
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
  rlist = pair.keys()
  do_nonblock = lambda fd : fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)
  do_nonblock(stdin_fd)
  do_nonblock(child_fd)
  select.select([child_fd],[],[]) #wait first child output and then change terminal settings
  termios.tcsetattr(stdout_fd, termios.TCSANOW, termios.tcgetattr(child_fd))
  while True:
    ready_fds = select.select(rlist,[],[])
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

def stub():
  port = int(sys.argv[1])
  executable = sys.argv[2]
  args = sys.argv[2:]
  pid,fd = pty.fork()
  if pid==0:
    do_child(executable,args)
  else:
    do_parent(port=port,child_fd=fd)


if __name__ == "__main__":
  stub()