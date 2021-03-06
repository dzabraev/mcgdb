#!/usr/bin/env python
#coding=utf8
import  pexpect,os,socket,subprocess,json,signal,select,\
        argparse,re,sys,pickle,time,pprint,imp,pysigset,\
        signal,termcolor,json

import pexpect.fdpexpect

from abc import abstractmethod, ABCMeta

from common import Gdb,FNULL, which
from runtest import is_valid_file

class UnknownControlSequence(Exception): pass

def open_sock():
  sock = socket.socket()
  sock.bind(('localhost',0))
  sock.listen(1)
  return sock, sock.getsockname()[1]

#XTERM=which('xterm')
XTERM=which('gnome-terminal')
PYTHON=which('python')
IOSTUB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'iostub.py')

ESC='\x1b'
CSI=ESC+'['

def split_first(s,ch='\n'):
  spl=s.split(ch)
  return spl[0], ch.join(spl[1:])

class WindowDead(Exception): pass
class AllWinClosed(Exception): pass

class XtermSpawn(object):
  __metaclass__ = ABCMeta

  def __init__(self,xterm,executable,journal,name,print_tokens=False,env=None,*args,**kwargs):
    if env is not None:
      self.env=env
    else:
      self.env={}
    self.print_tokens = print_tokens
    self.xterm=xterm #executable
    self.journal = journal
    self.name = name
    self.executable=executable
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

  def get_executable(self):
    return self.executable


  def _recv(self):
    n=1024
    while True:
      cnt=0
      s = self.xconn.recv(n)
      if not s:
        raise WindowDead
        #yield None
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
      if self.print_tokens:
        print repr(token)
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
    env_fname = '.environ'
    with open(env_fname,'wb') as f:
      f.write(json.dumps(environ))
    cmd='''{XTERM} -e "sh -c \\"{PYTHON} {IOSTUB} --executable={EXECUTABLE} {EXEC_ARGS} {ENVIRON} --xport={XPORT} --pport={PPORT}\\""'''.format(
      XTERM=self.xterm,
      PYTHON=PYTHON,
      IOSTUB=IOSTUB,
      EXECUTABLE=self.get_executable(),
      EXEC_ARGS = '' if not exec_args  else '''--args '{}' '''.format(exec_args),
      ENVIRON = '' if not environ  else '--env %s' % env_fname,
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
    env = dict(os.environ)
    env['TERM']='xterm'
    env.update(self.env)
    return env

  def journal_add_stream(self,data):
    self.journal.append({'stream':data, 'name':self.name})



class XtermMcgdbWin(XtermSpawn):
  def __init__(self,xterm,executable,exec_args,journal,name,*args,**kwargs):
    self.exec_args = exec_args
    super(XtermMcgdbWin,self).__init__(xterm,executable,journal,name,*args,**kwargs)

  def get_exec_args(self):
    return self.exec_args

  def send(self,msg):
    self.pconn.send(msg)

  def sendwin(self,msg):
    self.xconn.send(msg)

  def _feed(self):
    # https://www.xfree86.org/4.8.0/ctlseqs.html
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
            raise UnknownControlSequence
          current+=char
          char = yield
          while char.isdigit(): #column
            current+=char
            char = yield
          if char != ';':
            raise UnknownControlSequence
          current+=char
          char = yield
          while char.isdigit(): #row
            current+=char
            char = yield
          if char not in  'mM':
            raise UnknownControlSequence
          current+=char
          self.journal_add_stream(current)
          continue
        elif char.isdigit():
          current=CSI
          while char.isdigit():
            current+=char
            char = yield
          if char=='~':
            #PageUp, PageDown
            current+=char
            self.journal_add_stream(current)
            continue
          else:
            raise UnknownControlSequence
          raise UnknownControlSequence
        else:
          raise UnknownControlSequence
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
  def __init__(self,*args,**kwargs):
    self.saved=''
    super(XtermGdb,self).__init__(*args,**kwargs)

  def spawn(self):
    super(XtermGdb,self).spawn()
    self.program = pexpect.fdpexpect.fdspawn(self.pconn.fileno())

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

def open_window(xterm,gdb,journal,name,print_tokens=False,valgrind=None):
  if valgrind==None:
    executable,args = split_first(gdb.open_window_cmd(name),' ')
  else:
    executable=which('valgrind')
    args = '--log-file=%s' % valgrind + ' ' + gdb.open_window_cmd(name)
  return XtermMcgdbWin(xterm,executable,args,journal,name,print_tokens=print_tokens)

class Journal(object):
  def __init__(self,journal=[],print_records=False):
    self.data=journal
    self.print_records=print_records
    self.mouse_down = re.compile('\x1b\[<\d+;\d+;\d+M')
    self.mouse_up = re.compile('\x1b\[<\d+;\d+;\d+m')
  def append(self,x):
    if self.print_records:
      print repr(x)
    self.data.append(x)
  def save(self,fname=None):
    self.concat()
    self.enumerate()
    with pysigset.suspended_signals(signal.SIGCHLD):
      logfile = open(fname,'wb') if fname else sys.stdout
      logfile.write('journal='+str(self))
      logfile.close()
  def __concat_click(self,x,y):
    last=x[-1]
    ys = y.get('stream')
    ls = last.get('stream')
    if ys is not None and ls is not None and last['name']==y['name'] and self.mouse_down.match(ls) and self.mouse_up.match(ys) and ys[:-1]==ls[:-1]:
      last['stream']+=y['stream']
      return x[:-1] + [last]
    else:
      return x+[y]
  def __concat_sigwinch(self,x,y):
    last=x[-1]
    ysig = y.get('sig')
    xsig = last.get('sig')
    if last['name']==y['name'] and ysig==xsig==signal.SIGWINCH and last.get('time')-y.get('time')<0.1:
      return x[:-1] + [y]
    else:
      return x+[y]

  def enumerate(self):
    for idx,x in enumerate(self.data,1):
      x['action_num'] = idx

  def __concat_auxinput(self,x,y):
    x0=x[-1]
    if not ('stream' in x0 and 'stream' in y and x0['name']=='aux' and x0['stream'][-1]=='\n'):
      return x+[y]
    s=y['stream']
    if y['name']=='aux' and len(s)==1 and ord(s) < 128:
      x0['stream'] = y['stream']+x0['stream']
      return x
    else:
      return x+[y]

  def concat(self):
    if len(self.data)==0:
      return
    self.data = reduce(self.__concat_click,self.data[1:],[self.data[0]])
    self.data = reduce(self.__concat_sigwinch,self.data[1:],[self.data[0]])
    self.data = list(reversed(reduce(self.__concat_auxinput,reversed(self.data[:-1]),[self.data[-1]])))

  def __str__(self):
    self.concat()
    self.enumerate()
    return pprint.pformat(self.data,width=1)

def save_variables(fname,variables):
  with open(fname,'w') as f:
    for name,value in variables.iteritems():
      f.write('%s=%s\n\n' % (name,value))

def main():
  os.environ['LANG']='C'
  parser=argparse.ArgumentParser()
  parser.add_argument('output',default='record.py',nargs='?')
  parser.add_argument('--addwin',action='append',choices=['aux','src','asm'],help='if no specified all win will be open')
  parser.add_argument('--play',help='this parameter represents filename. From given file script will read and play actions. After execution of all actions recording will start.')
  parser.add_argument('--delay',help='only affects with --play', type=float, default=1)
  parser.add_argument('--print_actions',action='store_true')
  parser.add_argument('--mcgdb',help='path to mcgdb',
    default=os.path.join(os.path.dirname(os.getcwd()),'mcgdb'),
    type=lambda x: is_valid_file(parser, x),
  )
  parser.add_argument('--print_records',help='print input from windows', action='store_true')
  parser.add_argument('--print_tokens',help='print not cookied records', action='store_true')
  parser.add_argument('--xterm',choices=['xterm','gnome-terminal'],default='gnome-terminal')
  parser.add_argument('--coverage',nargs='?',const=os.path.abspath(os.path.join(os.path.dirname(__file__),'.coveragerc')))
  parser.add_argument('--valgrind',nargs='?',const=os.path.abspath(os.path.join(os.path.dirname(__file__),'valgrind-')))
  parser.add_argument('--coredump',nargs='?',const=os.path.abspath(os.path.dirname(__file__)))
  args = parser.parse_args()
  ENV=dict(os.environ)
  if args.coverage:
    ENV['COVERAGE']=args.coverage
  if args.valgrind:
    print 'save valgrind log to: %s' % args.valgrind
  if args.coredump:
    ENV['COREDUMP']=args.coredump
  xterm = distutils.spawn.find_executable(args.xterm)
  print 'start recording to {}'.format(args.output)
  journal_kwargs={
    'print_records':args.print_records,
  }
  if args.play:
    records_py = imp.load_source('records_py',args.play)
    if hasattr(records_py,'journal'):
      journal=Journal(records_py.journal,**journal_kwargs)
    else:
      journal=Journal(**journal_kwargs)
  else:
    records_py=None
    journal=Journal(**journal_kwargs)


  if args.addwin:
    win_names = args.addwin
  else:
    if records_py:
      win_names=records_py.windows
    else:
      win_names = ['aux','src','asm']
  win_names = list(set(win_names))
  print 'type Ctrl+C for stop recording'
  gdb=XtermGdb(xterm=xterm,journal=journal,name='gdb',executable=args.mcgdb,env=ENV)
  wins = dict(gdb=gdb,**{name:open_window(xterm,gdb,journal,name,
      print_tokens=args.print_tokens,valgrind=args.valgrind) for name in win_names})
  entities=dict(map(lambda x:(x.get_feed_fd(),x), wins.values()))
  rlist=list(entities.keys())
  program_fds=list(map(lambda x:x.get_program_fd(), wins.values()))
  if args.play:
    for record in journal.data:
      name=record['name']
      if name!='gdb' and name not in win_names:
        print '{} contains name {} but only {} can be open'.format(args.play,record['name'],win_names)
        sys.exit(0)
    print 'Dont touch windows until replay do not end'
    record_cnt=0
    record_total = len(journal.data)
    for record in journal.data:
      record_cnt+=1
      if args.print_actions:
        print '{: 5d}/{: 5d} {}'.format(record_cnt,record_total,repr(record))
      else:
        print '\r{: 5d}/{: 5d}'.format(record_cnt,record_total),
      sys.stdout.flush()
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
        ready,[],[] = select.select(rlist+program_fds,[],[],d)
        for fd in ready:
          if fd in rlist:
            print termcolor.colored('WARNING: interaction with program detected while reproduce actions','red')
          rd=os.read(fd,1024) #clear buffer
          print 'ignore input: %s' % repr(rd)
          #entities[fd].read(1024) #clear buffer
    print 'replay end. you can tocuh widnows.'

  try:
    while True:
      if len(rlist)==0:
        raise AllWinClosed
      ready,[],[] = select.select(rlist+program_fds,[],[])
      for fd in ready:
        if fd in program_fds:
          os.read(fd,1024) #clear buffer
        else:
          try:
            entities[fd].recvfeed()
          except WindowDead:
            rlist.remove(fd)
  except (KeyboardInterrupt,AllWinClosed):
    variables={
      'windows':win_names,
      'journal':journal,
    }
    save_variables(args.output,variables)


if __name__ == "__main__":
  main()
