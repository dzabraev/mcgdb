#!/usr/bin/env python
#coding=utf8
import pexpect,os,socket,subprocess,json,signal,select,argparse,re,sys,pickle,time,pprint
import pexpect.fdpexpect

import distutils.spawn
which = distutils.spawn.find_executable

from abc import abstractmethod, ABCMeta

from common import Gdb,FNULL

def open_sock():
  sock = socket.socket()
  sock.bind(('localhost',0))
  sock.listen(1)
  return sock, sock.getsockname()[1]

#XTERM=which('xterm')
XTERM=which('gnome-terminal')
PYTHON=which('python')
IOSTUB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'iostub.py')
GDB=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'mcgdb')

ESC='\x1b'
CSI=ESC+'['

def split_first(s,ch='\n'):
  spl=s.split(ch)
  return spl[0], ch.join(spl[1:])

class XtermSpawn(object):
  __metaclass__ = ABCMeta

  def __init__(self,journal,name):
    self.journal = journal
    self.name = name
    gen_recv = self._recv()
    self.recv = gen_recv.next
    gen_recv_json = self._recv_json()
    self.recv_json = gen_recv_json.next
    self.feed = self._feed()
    self.feed.next()
    self.spawn()
    self.recvfeed = self._recvfeed().next

  @abstractmethod
  def _feed(self): pass

  @abstractmethod
  def get_executable(self): pass


  def _recv(self):
    n=1024
    while True:
      cnt=0
      s = self.xconn.recv(n)
      if not s:
        yield None
      total=len(s)
      while cnt<total:
        yield s[cnt]
        cnt+=1

  def _recv_json(self):
    while True:
      data=''
      while True:
        b=self.recv()
        if not b:
          yield None
          continue
        if b=='\n':
          break
        data+=b
      token = json.loads(data)
      yield token


  def _recvfeed(self):
    while True:
      token = self.recv_json()
      if not token:
        yield
        continue
      if 'stream' in token:
        stream = token['stream'].encode('utf8')
        for ch in stream:
          self.feed.send(ch)
        yield
      elif 'sig' in token:
        token['name']=self.name
        self.journal.append(token)
        yield


  def spawn(self):
    self.xsock,self.xport = open_sock()
    self.psock,self.pport = open_sock()
    exec_args = self.get_exec_args()
    environ = self.get_environ()
    cmd='''{XTERM} -e "sh -c \\"{PYTHON} {IOSTUB} --executable={EXECUTABLE} {EXEC_ARGS} {ENVIRON} --xport={XPORT} --pport={PPORT}; sleep 999\\""'''.format(
      XTERM=XTERM,
      PYTHON=PYTHON,
      IOSTUB=IOSTUB,
      EXECUTABLE=self.get_executable(),
      EXEC_ARGS = '' if not exec_args  else '''--args '{}' '''.format(exec_args),
      ENVIRON = '' if not environ  else '--env {}'.format(','.join(map(lambda x:'{}:{}'.format(x[0],x[1]),environ.iteritems()))),
      XPORT=self.xport,
      PPORT=self.pport,
    )
    self.proc = subprocess.Popen(cmd,shell=True,stdout=FNULL,stderr=FNULL)
    self.pconn = self.psock.accept()[0]
    self.xconn = self.xsock.accept()[0]

  def get_feed_fd(self):
    return self.xconn.fileno()

  def get_program_fd(self):
    return self.pconn.fileno()

  def get_exec_args(self):
    return None

  def get_environ(self):
    return {'TERM':'xterm'}

  def journal_add_stream(self,data):
    self.journal.append({'stream':data, 'name':self.name})



class XtermMcgdbWin(XtermSpawn):
  def __init__(self,executable,exec_args,journal,name):
    self.executable = executable
    self.exec_args = exec_args
    super(XtermMcgdbWin,self).__init__(journal,name)

  def get_executable(self):
    return self.executable
  def get_exec_args(self):
    return self.exec_args

  def send(self,msg):
    self.pconn.send(msg)

  def sendwin(self,msg):
    self.xconn.send(msg)

  def _feed(self):
    while True:
      char = yield
      if char == ESC:
        char = yield
        if char == '[':
          char = CSI
        elif char == 'O':
          current=ESC+'O'
          current+=yield
          self.journal_add_stream(current)
          continue
        else:
          self.journal_add_stream(ESC+char)
          continue
      if char == CSI:
        char = yield
        if char=='<': #button push or release
          current=CSI+'<'
          char = yield
          while char.isdigit(): #button number
            current+=char
            char = yield
          if char != ';':
            continue #ERROR
          current+=char
          char = yield
          while char.isdigit(): #column
            current+=char
            char = yield
          if char != ';':
            continue #ERROR
          current+=char
          char = yield
          while char.isdigit(): #row
            current+=char
            char = yield
          if char not in  'mM':
            continue #ERROR
          current+=char
          self.journal_add_stream(current)
          continue
      else:
        #wait whole unicode character
        current=char
        while True:
          assert len(current)<=6
          try:
            current.decode('utf8')
            self.journal_add_stream(current)
            break
          except UnicodeDecodeError:
            pass
          current+=yield


class XtermGdb(XtermSpawn,Gdb):
  def __init__(self,journal,name):
    self.saved=''
    super(XtermGdb,self).__init__(journal,name)

  def spawn(self):
    super(XtermGdb,self).spawn()
    self.program = pexpect.fdpexpect.fdspawn(self.pconn.fileno())

  def get_executable(self):
    return GDB
  def get_environ(self):
    env = super(XtermGdb,self).get_environ()
    env['WIN_LIST']=''
    return env


  def kill(self):
    os.kill(self.proc.pid,signal.SIGTERM)
    os.system('killall -9 gdb')

  def _feed(self):
    while True:
      current = ''
      while True:
        char = yield
        if char == '\n':
          self.journal_add_stream(current)
          break
        elif char=='\x03': #Ctrl+C
          self.journal_add_stream('\x03')
          break
        current+=char

def open_window(gdb,journal,name):
  executable,args = split_first(gdb.open_window_cmd(name),' ')
  return XtermMcgdbWin(executable,args,journal,name)

class Journal(object):
  def __init__(self,journal=[]):
    self.data=journal
    self.mouse_down = re.compile('\x1b\[<\d+;\d+;\d+M')
    self.mouse_up = re.compile('\x1b\[<\d+;\d+;\d+m')
  def append(self,x):
    #print repr(x)
    self.data.append(x)
  def save(self,fname=None):
    self.concat()
    cnt=1
    for x in self.data:
      x['action_num'] = cnt
      cnt+=1
    logfile = open(fname,'wb') if fname else sys.stdout
    logfile.write('journal='+pprint.pformat(self.data,width=1))
    logfile.close()
  def __concat_click(self,x,y):
    last=x[-1]
    ys = y.get('stream')
    ls = last.get('stream')
    if ys is not None and ls is not None and self.mouse_down.match(ls) and self.mouse_up.match(ys) and ys[:-1]==ls[:-1]:
      last['stream']+=y['stream']
      return x[:-1] + [last]
    else:
      return x+[y]
  def __concat_sigwinch(self,x,y):
    last=x[-1]
    ysig = y.get('sig')
    xsig = last.get('sig')
    if ysig==xsig==signal.SIGWINCH and last.get('time')-y.get('time')<0.1:
      return x[:-1] + [y]
    else:
      return x+[y]

  def concat(self):
    self.data = reduce(self.__concat_click,self.data[1:],[self.data[0]])
    self.data = reduce(self.__concat_sigwinch,self.data[1:],[self.data[0]])

def main():
  parser=argparse.ArgumentParser()
  parser.add_argument('fname',default='record_log.py',nargs='?')
  parser.add_argument('--play',help='this parameter represents filename. From given file script will read and play actions. After execution of all actions recording will start.')
  parser.add_argument('--delay',help='only affects with --play', type=float, default=1)
  args = parser.parse_args()
  print 'start recording to {}'.format(args.fname)
  print 'type Ctrl+C for stop recording'
  if args.play:
    with open(args.play) as f:
      globs={}
      exec(f.read(),{},globs)
    if 'journal' in globs:
      journal=Journal(globs['journal'])
    else:
      journal=Journal()
  else:
    journal=Journal()
  gdb=XtermGdb(journal,'gdb')
  aux=open_window(gdb,journal,'aux')
  asm=open_window(gdb,journal,'asm')
  src=open_window(gdb,journal,'src')
  entities=dict(map(lambda x:(x.get_feed_fd(),x), [gdb,aux,asm,src]))
  rlist=list(entities.keys())
  if args.play:
    print 'Dont touch windows until replay do not end'
    wins={
      'gdb':gdb,
      'aux':aux,
      'src':src,
      'asm':asm,
    }
    program_fds=list(map(lambda x:x.get_program_fd(), [gdb,aux,asm,src]))
    record_cnt=0
    record_total = len(journal.data)
    for record in journal.data:
      record_cnt+=1
      print '\r{: 5d}/{: 5d}'.format(record_cnt,record_total)
      name=record['name']
      action_num = record['action_num']
      if 'stream' in record:
        wins[name].send(record['stream'].encode('utf8'))
      elif 'sig' in record:
        sig=record['sig']
        if sig==signal.SIGWINCH:
          wins[name].sendwin('\x1b[8;{rows};{cols}t'.format(rows=record['row'],cols=record['col']))
        else:
          raise NotImplementedError
      #collect window output
      t0 = time.time()
      while True:
        d = t0 - time.time() + args.delay
        if d<=0:
          break
        ready,[],[] = select.select(rlist,[],[],d)
        for fd in ready:
          os.read(fd,1024) #clear buffer
          #entities[fd].read(1024) #clear buffer
    print 'replay end. you can tocuh widnows.'
  else:
    journal=Journal()
  try:
    while True:
      ready,[],[] = select.select(rlist,[],[])
      for fd in ready:
        entities[fd].recvfeed()
  except KeyboardInterrupt:
    journal.save(args.fname)


if __name__ == "__main__":
  main()
