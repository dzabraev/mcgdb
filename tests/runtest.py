#!/usr/bin/env python
#coding=utf8

import pexpect, subprocess, time, os, socket, sys, re, select
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

class TimeoutReached(Exception): pass

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


class NoEsc(object):
  def __init__(self,s):
    self.s=s
  def __str__(self):
    return self.s
  def __add__(self,a):
    if type(a) is NoEsc:
      a=str(a)
    else:
      a=re.escape(a)
    return NoEsc(self.s + a)

cts_esc='\x1b'

class ControlSequence(object):
  def __init__(self):
    # description of control sequences:
    # http://www.xfree86.org/4.7.0/ctlseqs.html#VT100%20Mode
    esc=NoEsc(cts_esc)

    C   = NoEsc('.')
    Ps  = NoEsc('\d+')
    Pm  = NoEsc('((\d+)|((\d+;)+\d+))')
    Pt  = NoEsc('[a-z]+')

    IND     =esc+'D'
    NEL     =esc+'E'
    HTS     =esc+'H'
    RI      =esc+'M'
    SS2     =esc+'N'
    SS3     =esc+'O'
    DCS     =esc+'P'
    SPA     =esc+'V'
    EPA     =esc+'W'
    SOS     =esc+'X'
    DECID   =esc+'Z'
    CSI     =esc+'['
    ST      =esc+'\\'
    OSC     =esc+']'
    PM      =esc+'^'
    APC     =esc+'_'

    SP=' '

    self.cts=[]
    #Controls beginning with ESC (other than those where ESC is part of a 7-bit equivalent to 8-bit C1 controls), ordered by the final character(s).
    self.cts+=[
      (esc,SP,'F'),
      (esc,SP,'G'),
      (esc,SP,'L'),
      (esc,SP,'M'),
      (esc,SP,'N'),
      (esc,'#3'),
      (esc,'#4'),
      (esc,'#5'),
      (esc,'#6'),
      (esc,'#7'),
      (esc,'#8'),
      (esc,'%@'),
      (esc,'%G'),
      (esc,'(',C),
      (esc,')',C),
      (esc,'*',C),
      (esc,'+'),
      (esc,'7'),
      (esc,'8'),
      (esc,'='),
      (esc,'>'),
      (esc,'F'),
      (esc,'c'),
      (esc,'l'),
      (esc,'m'),
      (esc,'n'),
      (esc,'o'),
      (esc,'|'),
      (esc,'}'),
      (esc,'~'),
    ]
    #Application Program-Control functions
    self.cts+=[
      (APC,Pt,ST),
    ]

    #Device-Control functions
    self.cts+=[
      (DCS, Ps, ';', Ps),
      (DCS, Ps, ';', Pt, ST),
      (DCS,'$','q',Pt,ST),
      (DCS,'+','q',Pt,ST),
    ]

    #Functions using CSI , ordered by the final character(s)
    self.cts+=[
      (CSI,Ps,'@'),
      (CSI,Ps,'A'),
      (CSI,Ps,'B'),
      (CSI,Ps,'C'),
      (CSI,Ps,'D'),
      (CSI,Ps,'E'),
      (CSI,Ps,'F'),
      (CSI,Ps,'G'),
      (CSI,Ps,';',Ps,'H'),
      (CSI,Ps,'I'),
      (CSI,Ps,'J'),
      (CSI,'?',Ps,'J'),
      (CSI,Ps,'K'),
      (CSI,'?',Ps,'K'),
      (CSI,Ps,'L'),
      (CSI,Ps,'M'),
      (CSI,Ps,'P'),
      (CSI,Ps,'S'),
      (CSI,Ps,'T'),
      (CSI,Ps,';',Ps,';',Ps),
      (CSI,Ps,';',Ps,'T'),
      (CSI,Ps,'X'),
      (CSI,Ps,'Z'),
      (CSI,Pm,'`'),
      (CSI,Ps,'b'),
      (CSI,Ps,'c'),
      (CSI,'>',Ps,'c'),
      (CSI,Pm,'d'),
      (CSI,Ps,';',Ps,'f'),
      (CSI,Ps,'g'),
      (CSI,Pm,'h'),
      (CSI,'?',Pm,'h'),
      (CSI,Pm,'i'),
      (CSI,'?',Pm,'i'),
      (CSI,Pm,'l'),
      (CSI,'?',Pm,'l'),
      (CSI,Pm,'m'),
      (CSI,Ps,'n'),
      (CSI,'?',Ps,'n'),
      (CSI,'!p'),
      (CSI,Ps,';',Ps,'"p'),
      (CSI,Ps,'"q'),
      (CSI,Ps,';',Ps,'r'),
      (CSI,'?',Pm,'r'),

    ]

    escape_regex = lambda x : re.escape(x) if type(x) is not NoEsc else str(x)
    self.regexes=[]
    self.cregexes=[]
    for cs in self.cts:
      reg=''.join(map(escape_regex,cs))
      reg='^('+reg+')$'
      self.regexes.append(reg)
      self.cregexes.append(re.compile(reg,re.MULTILINE|re.DOTALL))

  def is_control_sequence(self,text):
    for creg in self.cregexes:
      if creg.match(text):
        return True
    return False

  def get_regex(self):
    global_regex=''
    for cs_regex in self.regexes:
      global_regex+='('+cs_regex+')|'
    return re.compile(global_regex[:-1])

control_sequence = ControlSequence()

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

  def click(self,col,row):
    msg=self.mouse_click_msg(row,col)
    print msg
    self.conn.sendall(self.mouse_click_msg(row=row,col=col))

  def get_token(self,timeout=5):
    ''' return single charectar or control sequence
        http://www.xfree86.org/4.7.0/ctlseqs.html#Definitions
    '''
    seq=''
    b=self.conn.recv(1)
    if b!=cts_esc:
      return b
    seq+=b
    while True:
      rready,_,_ = select.select([self.conn.fileno()],[],[],timeout)
      if rready==[] and timeout!=None:
        raise TimeoutReached
      b=self.conn.recv(1)
      assert b != cts_esc, repr('unparsed: `{seq}`'.format(seq=seq))
      seq+=b
      if control_sequence.is_control_sequence(seq):
        return seq

  def get_changes(self,predicate,timeout=5):
    wd=WindowData()
    t0=time.time()
    while not predicate(wd):
      if time.time()-t0>timeout:
        raise TimeoutReached
      seq = self.get_control_seq()

  @cleanup__close__
  def close(self):
    self.xterm.kill()

class McgdbAuxWin(McgdbWin):
  pass

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

  def open_window_cmd(self,win_name):
    self.gdb.sendline('mcgdb open {win_name} --manually'.format(win_name=win_name))
    self.gdb.expect('Execute manually `(/.+/mcgdb_mc -e --gdb-port=\d+)` for start window')
    exec_cmd = self.gdb.match.groups()[0]
    return exec_cmd

  def open_aux_win(self):
    return McgdbAuxWin(self.open_window_cmd('aux'))

  @cleanup__close__
  def close(self):
    self.gdb.kill(9)


def runtest():
  gdb=Gdb('main')
  aux=gdb.open_aux_win()
  gdb.gdb.sendline('break main')
  gdb.gdb.sendline('run')
  while True:
    #print repr(aux.conn.recv(1024)),
    print repr(aux.get_token(timeout=None))
    sys.stdout.flush()

if __name__ == "__main__":
  runtest()
