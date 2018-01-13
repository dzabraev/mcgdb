#coding=utf8

import gdb
import sys,os,select,errno,socket,stat,time
import signal
import pysigset
import json
import logging
import threading, subprocess
import re,copy,ctypes


from mcgdb import PATH_TO_DEFINES_MCGDB
import mcgdb

from abc import ABCMeta, abstractmethod, abstractproperty

class FrmaeNotSelected(Exception): pass

TABID_TMP=1 #Временный экземпляр таблицы. Используется для выведения пользователю каких-либо сообщений.
#После того, как экземпляр был сделан текущим, и потом на место текущего экземпляра
#был установлен другой экземпляр, данный экземпляр будет удален.


main_thread_ident=threading.current_thread().ident
mcgdb_main=None

DEBUG       = os.environ.get('DEBUG')
VALGRIND    = os.environ.get('VALGRIND') #run gui window under valgrind
WIN_LIST    = os.environ.get('WIN_LIST',"aux src").split()
COVERAGE    = os.environ.get('COVERAGE')
COREDUMP    = os.environ.get('COREDUMP')
USETERM     = os.environ.get('USETERM')
WAITGDB     = os.environ.get('WAITGDB')

pending_errors={}

def setup_logging(DEBUG):       # pragma: no cover
  global debug_messages         # pragma: no cover
  global debug_level            # pragma: no cover
  if DEBUG is not None:         # pragma: no cover
    debug_level = logging.INFO  # pragma: no cover
    debug_messages=False         # pragma: no cover
    if os.path.exists(DEBUG):   # pragma: no cover
      os.remove(DEBUG)          # pragma: no cover
    logging.basicConfig(        # pragma: no cover
      filename=DEBUG,           # pragma: no cover
      format = u'[%(module)s LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s', # pragma: no cover
      level = debug_level)      # pragma: no cover
    cmd='''gnome-terminal -e 'tail -f %s' &''' % DEBUG # pragma: no cover
    os.system(cmd) # pragma: no cover
    #proc=subprocess.Popen(cmd, shell=True) # pragma: no cover
    #proc.wait()
    #rc=proc.returncode
  else:                         # pragma: no cover
    debug_level = logging.CRITICAL    # pragma: no cover
    debug_messages = False      # pragma: no cover
    logging.basicConfig(        # pragma: no cover
      format = u'[%(module)s LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s', # pragma: no cover
      level = debug_level)      # pragma: no cover

def setup_coverage(fname):              # pragma: no cover
  import coverage                       # pragma: no cover
  kwargs={}                             # pragma: no cover
  if fname:                             # pragma: no cover
    kwargs['config_file']=fname         # pragma: no cover
  cov = coverage.Coverage(**kwargs)     # pragma: no cover
  cov.start()                           # pragma: no cover
  import atexit                         # pragma: no cover
  def stop_coverage(cov):               # pragma: no cover
    cov.stop()                          # pragma: no cover
    cov.save()                          # pragma: no cover
    cov.html_report()                   # pragma: no cover
  atexit.register(lambda :stop_coverage(cov)) # pragma: no cover



if COVERAGE is not None:              # pragma: no cover
  setup_coverage(COVERAGE)            # pragma: no cover
setup_logging(DEBUG)


class mcgdbBaseException(Exception):
  def __init__(self, value=None):
    self.value = value

  def __str__(self):
    return str(self.value)

class mcgdbChangevarErr(Exception):
  def __init__(self, error_msg, path, need_update=None):
    self.error_msg = error_msg
    self.path = path
    self.need_update = need_update

  def __str__(self):
    return str(self.error_msg)

class InferiorNotAlive(mcgdbBaseException): pass

class ValueUnavailable(Exception):
  default_stub = '<unavailable>'

def exec_main(f):
  def decorated(*args,**kwargs):
    return exec_in_main_pythread (f,args,kwargs)
  return decorated


@exec_main
def if_gdbstopped_else(stopped=None,running=None):
  flag,cb = (True,stopped) if gdb_stopped() else (False,running)
  res = cb() if cb else None
  return flag,res

def exec_on_gdb_stops(callback):
  def unregister(*args,**kwargs):
    callback(*args,**kwargs)
    gdb.events.stop.disconnect(unregister)
  gdb.events.stop.connect(unregister)

import mcgdb.gdb2 as gdb2


class MCGDB_VERSION(object):
  major=1
  minor=4

class Index(object):
  def __init__(self):
    self.drop()
    self.counter=1

  def insert(self,key,data=None):
    old = self.index_data.get(key)
    if old==None:
      idx=self.counter
      self.counter+=1
    else:
      idx,_ = old
    self.index_data[key] = (idx,data)
    self.index_key[idx] = data
    return idx

  def get(self,key):
    cv=self.index_data.get(key)
    if cv==None:
      return None,None
    else:
      return cv

  def get_by_idx(self,idx):
    return self.index_key[idx]

  def __call__(self,*args,**kwargs):
    return self.insert(*args,**kwargs)

  def drop(self):
    self.index_data={}
    self.index_key={}

INDEX=Index()
INDEX_tmp=Index() #данный индекс будет очищатсья вместе с value_cache

def valueaddress_to_ulong(value):
  if value==None:
    return None
  return ctypes.c_ulong(long(value)).value


def get_this_frame_num():
  frame=gdb.selected_frame()
  if frame==None:
    return None
  cnt=0
  while frame:
    cnt+=1
    try:
      frame=frame.newer()
    except gdb.error:
      #if gdb reached remote protocol timeout and can't read registers
      #then frame can be invalid.
      return None
  return cnt

def get_this_thread_num():
  thread = gdb.selected_thread()
  if thread:
    return thread.ptid[1]
  else:
    return None

def stringify_value(value,enable_additional_text=False, integer_mode=None, **kwargs):
  '''Конвертация gdb.Value в строку
    Args:
      **enable_additional_text (bool):
        Если True, то будет печататься нечто вроде 
        0x1 <error: Cannot access memory at address 0x1>
        Если False,
        то 0x1
  '''
  if value.is_optimized_out:
    return '<OptimizedOut>'
  type_code = value.type.strip_typedefs().code
  try:
    if type_code==gdb.TYPE_CODE_INT and integer_mode in ('dec','hex','bin') and value.type.strip_typedefs().sizeof<=8:
      bitsz=value.type.sizeof*8
      #gdb can't conver value to python-long if sizeof(value) > 8
      if integer_mode=='dec':
        return str(long(value))
      elif integer_mode=='hex':
        pattern='0x{{:0{hexlen}x}}'.format(hexlen=bitsz/4)
        return pattern.format(ctypes.c_ulong(long(value)).value)
      elif integer_mode=='bin':
        pattern='{{:0{bitlen}b}}'.format(bitlen=bitsz)
        return pattern.format(ctypes.c_ulong(long(value)).value)
    if type_code in (gdb.TYPE_CODE_PTR,) and not enable_additional_text:
      return hex(ctypes.c_ulong(long(value)).value)[:-1]
    else:
      #например, если делать unicode или str для `.*char *`, то память будет читаться дважды.
      return unicode(value)
  except (gdb.error, gdb.MemoryError, MemoryError):
    raise ValueUnavailable


#def stringify_value_safe(*args,**kwargs):
#  try:
#    return stringify_value(*args,**kwargs)
#  except gdb.MemoryError:
#    return 'Cannot access memory'
#  except ValueUnavailable:
#    return ValueUnavailable.default_stub




class GdbValueCache(object):
  def __init__(self):
    self.drop()

  def drop(self):
    ''' Drop all cache layers
    '''
    self.value_cache = {}
    self.value_str_cache = {}

#  def cached_stringify_value(self,value,path,**kwargs):
#    frnum=get_this_frame_num()
#    if frnum==None:
#      valcache=None
#    else:
#      key=(frnum,path)
#      valcache=self.value_str_cache.get(key)
#    if valcache==None:
#      valcache=stringify_value_safe(value,**kwargs)
#      self.value_str_cache[key]=valcache
#    return valcache


  def valcache(self,value_or_path,**kwargs):
    '''return value from cache if exists else return argument value'''
    if type(value_or_path) in (str,unicode):
      path=value_or_path
      frnum=get_this_frame_num()
      th=gdb.selected_thread()
      if frnum==None or th==None:
        valcache1=None
      else:
        key=(frnum,path,th.global_num)
        valcache1=self.value_str_cache.get(key)
      if valcache1==None:
        valcache1=gdb.parse_and_eval(path)
        self.value_cache[key]=valcache1
        self.add_valcache_byaddr(valcache1)
    else:
      value=value_or_path
      if value.is_optimized_out:
        #can't cache this value
        return value
      addr=valueaddress_to_ulong(value.address)
      if addr==None:
        return value
      key=(addr,str(value.type))
      valcache1=self.value_cache.get(key)
      if valcache1==None:
        self.add_valcache_byaddr(value)
        valcache1=value
    return valcache1

  def __call__(self,*args,**kwargs):
    return self.valcache(*args,**kwargs)

  def add_valcache_byaddr(self,value):
    addr=valueaddress_to_ulong(value.address)
    if addr==None:
      return False
    key=(addr,str(value.type))
    self.value_cache[key]=value
    return True



value_cache = GdbValueCache()
#cached_stringify_value = value_cache.cached_stringify_value
valcache = value_cache








def gdb_print(msg):
  gdb.post_event(lambda : gdb.write(msg))

def gdbprint(*args):
  gdb_print(' '.join(map(unicode,args))+'\n')

def get_prompt():
  return gdb.parameter('prompt')


def get_gdb_version():
  match=re.match('(\d+)\.(\d+)(\.(\d+))?',gdb.VERSION)
  if not match:
    return (None,None,None)
  else:
    major,minor,micro_dot,micro = match.groups()
    conv=lambda x: int(x) if x!=None else x
    return (conv(major),conv(minor),conv(micro))


def is_gdb_version_correct():
  good_major=7
  good_minor=12
  major,minor,micro=get_gdb_version()
  if major==None or minor==None:
    gdb_print("WARNING: can't recognize gdb version. Version must be >= {ma}.{mi}\n".format(
      ma=major,mi=minor))
    return True
  if major < good_major:
    gdb_print("ERROR: gdb version must be >= {ma}.{mi}\n".format(
      ma=good_major,mi=good_minor))
    return False
  elif major == good_major and minor < good_minor:
    gdb_print("ERROR: gdb version must be >= {ma}.{mi}\n".format(
      ma=good_major,mi=good_minor))
    return False
  return True

def is_python_version_correct():
  if sys.version_info.major!=2 or sys.version_info.minor<7:
    gdb_print('ERROR: mcgdb use python 2.7, but you gdb compiled with {major}.{minor}.{micor}'.format(
      major=sys.version_info.major,
      minor=sys.version_info.minor,
      micro=sys.version_info.micro,
    ))
    gdb_print('ERROR: recompile gdb with `./configure --with-python=python2`')
    return False
  else:
    return True


def pkgsend(fd,msgs):
  #debug('SEND: {}'.format(str(msgs)))
  smsg=''
  if not type(msgs) in (list,tuple):
    msgs=[msgs]
  for msg in msgs:
    jmsg=json.dumps(msg)
    smsg+='{len};{data}'.format(len=len(jmsg),data=jmsg)
  n=0
  total=len(smsg)
  while n<total:
    n+=os.write(fd,smsg[n:])

def pkgrecv(fd):
  lstr=''
  while True:
    try:
      b=os.read(fd,1)
    except IOError as e:
      if e.errno == errno.EINTR:
        continue
      else:
        raise IOFailure
    except OSError:
      raise IOFailure
    if len(b)==0:
      raise IOFailure
    if b!=';':
      lstr+=b
    else:
      break
  assert len(lstr)>0
  total=int(lstr)
  nrecv=0
  data=''
  while nrecv<total:
    try:
      data1=os.read(fd,total-nrecv)
    except IOError as e:
      if e.errno == errno.EINTR:
        continue
      else:
        raise
    except OSError:
      raise IOFailure
    if len(data1)==0:
      raise IOFailure
    nrecv+=len(data1)
    data+=data1
  debug('RECV: {}'.format(data))
  return json.loads(data)



def is_main_thread():
  return threading.current_thread().ident==main_thread_ident


class IOFailure(Exception): pass

def debug(msg):
  global debug_level
  if debug_level==logging.DEBUG:
    #эта блокировка нужна, поскольку exec_in_main_pythread
    #делает блокировки. И лучше их избегать.
    exec_in_main_pythread (logging.debug,(msg,))

def error(msg):
  exec_in_main_pythread (logging.error,(msg,))


def gdb_stopped():
  try:
    th=gdb.selected_thread()
    if th==None:
      return True
    return gdb.selected_thread().is_stopped()
  except:
    return True

def exec_cmd_in_gdb(cmd):
  try:
    exec_in_main_pythread( gdb.execute, ('echo {cmd}\n'.format(cmd=cmd),False) )
    exec_in_main_pythread( gdb.execute, (cmd,) )
  except gdb.error:
    pass




class ThQueue(object):
  def __init__(self):
    self.mutex = threading.Lock()
    self.queue=[]
  def append(self,obj):
    self.mutex.acquire()
    self.queue.append(obj)
    self.mutex.release()
  def pop(self):
    self.mutex.acquire()
    obj=self.queue.pop(0)
    self.mutex.release()
    return obj

gdbevt_queue = ThQueue()

@exec_main
def get_bp_locations(bp):
  if bp.type!=gdb.BP_BREAKPOINT:
    return []
  location=bp.location
  try:
    locs=gdb.decode_line(location)[1]
  except gdb.error:
    #current file have not location `location` then produce this error
    return []
  if locs==None:
    return []
  locations=[]
  if locs:
    for loc in locs:
      line=loc.line
      if not loc.symtab:
        #maybe breakpoint have not location. For ex. `break exit`, `break abort`
        continue
      filename=loc.symtab.fullname()
      locations.append( (filename,line) )
  return locations

def touch_breakpoint(bp):
  'generate modification event without bp modification'
  bp.enabled = bp.enabled

class BpModif(object):
  def __init__(self):
    self.need_delete=[]
    self.need_update={}
    self.key_to_bpid={}
    self.bpid_to_bp={}
    gdb.events.breakpoint_created.connect(self.__add_bp)
    gdb.events.breakpoint_deleted.connect(self.__del_bp)

  def __add_bp(self,bp):
    self.bpid_to_bp[bp.number]=bp

  def __del_bp(self,bp):
    pass
    #if bp.number in self.bpid_to_bp:
    #  del self.bpid_to_bp[bp.number]

  def delete(self,win_id,external_id,number=None):
    assert external_id is not None
    key=(win_id,external_id)
    if key in self.need_update:
      del self.need_update[key]
    gdb_bpid = self.key_to_bpid.pop(key,number)
    #if BP added through gdb (not gui) => key does not correspond any gdb_bp_id
    if gdb_bpid is not None:
      self.need_delete.append(gdb_bpid)
      return gdb_bpid
    else:
      return None #bp does not exist

  def update(self,win_id,external_id,enabled=None,silent=None,
                  ignore_count=None,temporary=None,thread=None,
                  condition=None,commands=None,create_loc=None,
                  number=None,after_create=None):
    assert external_id is not None
    key=(win_id,external_id)
    if key in self.need_delete:
      self.need_delete.remove(key)
    self.need_update[key] = (win_id,enabled,silent,ignore_count,temporary,thread,condition,commands,create_loc,number,after_create)
    if number is not None:
      self.key_to_bpid[key]=number

  def process(self):
    for bpid in self.need_delete:
      bp=self.bpid_to_bp.get(bpid)
      if bp is not None:
        bp.delete()
        if bpid in self.bpid_to_bp:
          del self.bpid_to_bp[bpid]
    self.need_delete=[]
    for key,values in self.need_update.items():
      bp_was_touched = False
      win_id,enabled,silent,ignore_count,temporary,thread,condition,commands,create_loc,number,after_create = values
      bpid = number if number is not None else self.key_to_bpid.get(key)
      if bpid is not None and bpid in self.bpid_to_bp:
        #bp exists
        #bpid can't be None, but breakpoint may be deleted
        bp=self.bpid_to_bp[bpid]
      else:
        #not exists, create
        assert create_loc is not None
        kw={
          'spec':create_loc,
          'type':gdb.BP_BREAKPOINT,
        }
        if temporary is not None:
          kw['temporary']=temporary
        bp=gdb.Breakpoint(**kw)
        bp_was_touched = True
        self.key_to_bpid[key]=bp.number
        self.bpid_to_bp[bp.number]=bp
        if after_create is not None:
          after_create(bp)

      if enabled is not None and bp.enabled!=enabled:
        bp.enabled=enabled
        bp_was_touched = True
      if silent is not None and bp.silent!=silent:
        bp.silent=silent
        bp_was_touched = True
      if ignore_count is not None and bp.ignore_count!=ignore_count:
        bp.ignore_count=ignore_count
        bp_was_touched = True
      if thread==-1:
        thread=None
      if bp.thread != thread:
        bp.thread=thread
        bp_was_touched = True
      if bp.condition!=condition:
        try:
          bp.condition=condition
        except gdb.error as e:
          pending_errors[win_id].append(str(e))
      if not bp_was_touched:
        touch_breakpoint(bp)
      if bp.commands!=commands:
        gdb.write('WARNING: parameter commands is not supported by front-end.\nYou can set him manually:\ncommands {number}\n{commands}\n'.format(
          number=bp.number,commands=commands))
    self.need_update={}


bpModif=BpModif()



@exec_main
def inferior_alive ():
  return not gdb.selected_thread()==None

def exec_in_main_pythread(func,args=(),kwargs={}):
  #Данную функцию нельзя вызывать более чем из одного потока
  if is_main_thread():
    return func(*args,**kwargs)
  result = {}
  evt=threading.Event()

  def exec_in_main_pythread_1(func,args,kwargs,evt,result):
    try:
      result['retval']=func(*args,**kwargs)
      result['succ']='ok'
    except Exception:
      result['succ']='exception'
      result['except'] = sys.exc_info()
    evt.set()

  gdb.post_event(
      lambda : exec_in_main_pythread_1(func,args,kwargs,evt,result)
  )
  evt.wait()
  if result['succ']=='ok':
    return result['retval']
  else:
    exc_type, exc_value, exc_traceback = result['except']
    raise exc_type, exc_value, exc_traceback





class GEThread(object):
  def __init__(self,gdb_rfd,main_thread_ident):
    self.gdb_rfd=gdb_rfd
    self.main_thread_ident=main_thread_ident
    self.fte={}
    self.WasCalled=False
    self.exec_filename=None
    self.exec_line=None
    self.wait_connection={}

  def __open_window(self, pkg):
    # Процесс открывания окна следующий. Создается класс, в рамках которого есть
    # listen port, затем открывается окно (напр, с редактором), этому окну дается
    # номер listen port'a. Данный порт записывается в хэш self.wait_connection.
    # Смысл self.wait_connection в том, что окно может не открыться в результате
    # каких-то внешних причин, не зависящих от нас. И будет плохо, если исполнение
    # данного потока заблокируется в ожидании соединения. После детектирования 
    # запроса на установления соединения будет вызван метод window.process_connection
    # и window переместится из self.wait_connection в self.fte
    import  mcgdb.srcwin, mcgdb.auxwin, mcgdb.asmwin
    type=pkg['type']
    manually=pkg.get('manually',False)
    cls={
      'src': mcgdb.srcwin.SrcWin,
      'aux': mcgdb.auxwin.AuxWin,
      'asm': mcgdb.asmwin.AsmWin,
    }
    WinClsConstr=cls[type]
    if WinClsConstr==None:
      debug('bad `type`: `{}`'.format(pkg))
    else:
      window=WinClsConstr(manually=manually)
      self.wait_connection[window.listen_fd] = window

  def get_pkg_from_gdb(self):
    ''' Прием пакета от gdb.

        Если пакет предназначается только для GEThread, то пакет будет обработан и
        будет возвращен None.
        Если пакет предназначается для классов, которые представляют окна, то будет
        возвращен пакет.
    '''
    pkg=pkgrecv(self.gdb_rfd)
    cmd=pkg['cmd']
    if debug_messages:
      logging.info('time={t} sender=gdb cmd={cmd}'.format(t=time.time(),cmd=(pkg[cmd] if cmd in pkg else cmd)))
    if cmd=='open_window':
      self.__open_window(pkg)
      return
    elif cmd=='gdbevt':
      evtname,evt=gdbevt_queue.pop()
      new_pkg={'cmd':'gdbevt','gdbevt':evtname,'evt':evt}
      if evtname in ('exited','stop','new_objfile','clear_objfiles','memory_changed','register_changed'):
        value_cache.drop()
        INDEX_tmp.drop()
      return new_pkg
    elif cmd=='stop_event_loop':
      for fd,win in self.fte.iteritems():
        win.terminate()
      sys.exit(0)
    else:
      return pkg

  def get_pkg_from_remote(self,fd):
    pkg = pkgrecv(fd)
    #gdb_print(str(pkg)+'\n')
    cmd=pkg['cmd']
    if debug_messages:
      logging.info('time={t} sender=guiwin cmd={cmd}'.format(t=time.time(),cmd=(pkg[cmd] if cmd in pkg else cmd)))
    if cmd=='exec_in_gdb':
      if gdb_stopped():
        command_for_exec_in_gdbshell=pkg['exec_in_gdb']
        try:
          gdb2.execute(command_for_exec_in_gdbshell)
        except gdb.error:
          return None
      else:
        return None
    return pkg


  def send_pkg_to_entities (self, pkg, entity_key=None):
    cmd=pkg['cmd']
    if debug_messages:
      logging.info('time={time} sendToEntities cmd={cmd}'.format(cmd=(pkg[cmd] if cmd in pkg else cmd),time=time.time()))
    else:
      died_entity=[]
      entity_keys = [entity_key] if entity_key is not None else self.fte.keys()
      for fd in entity_keys:
        if fd not in self.fte:
          #entity was died (meybe window was closed)
          continue
        entity=self.fte[fd]
        try:
          res = entity.process_pkg (pkg)
        except OSError:
          #windows was closed
          died_entity.append(fd)
          res=None
        if res:
          if debug_messages:
            logging.info('time={time} sender={type} pkgs={pkgs}'.format(type=entity.type,pkgs=res,time=time.time()))
          self.prepend_pkg_to_queue(res)
      for fd in died_entity:
        del self.fte[fd]

  def _process_connection(self,entity):
    try:
      ok=entity.process_connection()
    except OSError as e:
      gdb_print('Error while opening window: {}\n'.format(str(e)))
      ok=False
    if ok:
      self.fte[entity.fd]=entity

  def send_pending_errors(self):
    for entity in self.fte.values():
      errors=pending_errors.get(entity.get_key())
      while errors:
        entity.send_error(errors.pop(0))

  def __call__(self):
    assert not self.WasCalled
    self.WasCalled=True
    self.pending_pkgs=[] #Если target_running, а от gdb приходит event, например, new_objfile
    #и если при работающем target попытаться, например, обновить локальные переменные, то первое же
    #gdb.parse_and_eval() выбросит exception. Поэтому будем сохранять события от gdb пока не получим
    # 'exited' или 'stop'
    while True:
      if_gdbstopped_else(stopped=bpModif.process)
      self.send_pending_errors()
      rfds=self.fte.keys()
      rfds+=self.wait_connection.keys()
      rfds.append(self.gdb_rfd)
      timeout = None if self.pkg_queue_is_empty() else 0
      try:
        fds=select.select(rfds,[],[], timeout)
      except select.error as se:
        if se[0]==errno.EINTR:
          continue
        else:
          raise
      ready_rfds=fds[0]
      has_new_pkg=False
      for fd in ready_rfds:
        if fd in self.wait_connection.keys():
          entity=self.wait_connection.pop(fd)
          onstop,onrun=(lambda entity:
                          (lambda callback:
                            (callback,lambda *args,**kwargs:
                              exec_on_gdb_stops(callback)) )(lambda *args,**kwargs:
                                self._process_connection(entity)))(entity)
          #if gdb stopped execute process_connection at this time, else register process_connection
          #execute when gdb will be stopped
          if_gdbstopped_else(stopped=onstop,running=onrun)
          pending_errors[entity.get_key()] = []
          continue
        else:
          entity_key,pkg=None,None
          if fd==self.gdb_rfd:
            #обработка пакета из gdb
            pkg = self.get_pkg_from_gdb()
          else:
            try:
              pkg = self.get_pkg_from_remote(fd)
              logging.info('time={time} sender=remote pkgs={pkgs}'.format(pkgs=pkg,time=time.time()))
              entity_key = fd
            except IOFailure:
              #probably remote window was clased =>
              #we need destroy corresponding entity
              entity=self.fte[fd]
              debug('connection type={} was closed'.format(entity.type))
              del self.fte[fd]
              entity.byemsg()
              entity=None #forgot reference to object
          if pkg:
            self.append_pkg_to_queue(pkg,entity_key)
            has_new_pkg=True
      if has_new_pkg:
        #first fetch all packages from sockets, then process it
        continue
      if not self.pkg_queue_is_empty():
        #process packages
        if_gdbstopped_else(stopped=self.process_pending_pkg)

    debug('event_loop stopped\n')

  def process_pending_pkg(self):
    pkg,entity_key = self.pending_pkgs.pop(0)
    self.send_pkg_to_entities(pkg,entity_key)

  def pkg_queue_is_empty(self):
    return len(self.pending_pkgs)==0

  def append_pkg_to_queue(self,*args,**kwargs):
    return self.put_pkg_into_queue(*args,append=True,**kwargs)

  def prepend_pkg_to_queue(self,*args,**kwargs):
    return self.put_pkg_into_queue(*args,append=False,**kwargs)

  def put_pkg_into_queue(self,pkg,entity_key=None,append=True):
    ''' If entity_key is None, then send pkg to all entities.
        Else send to self.fte[entity_key]
    '''
    prepend=not append
    pkgs = pkg if type(pkg) is list else [pkg]
    if prepend:
      pkgs = reversed(pkgs)
    for pkg in pkgs:
      if pkg is None:
        continue
      if 'gdbevt' in pkg:
        assert entity_key is None
        cmd=pkg['gdbevt']
        if cmd in ('stop',):
          self.drop_pending_pkgs(lambda pkg:'gdbevt' in pkg and pkg['gdbevt'] in ('stop','register_changed','memory_changed'))
        elif cmd in ('exited',):
          self.pending_pkgs[:] = [] #clear pending events
        #else:
        #  self.drop_pending_pkgs(lambda pkg:'gdbevt' in pkg and pkg['gdbevt']==cmd)
      if append:
        self.pending_pkgs.append((pkg,entity_key))
      else: #prepend
        self.pending_pkgs.insert(0,(pkg,entity_key))

  def drop_pending_pkgs(self,predicat):
    self.pending_pkgs = filter(lambda pkg__entity_key : not predicat(pkg__entity_key[0]), self.pending_pkgs)


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class McgdbMain(object):
  __metaclass__ = Singleton
  def __init__(self):
    if not is_gdb_version_correct():
      return
    if not is_python_version_correct():
      return
    gdb_print('\nmcgdb version: {major}.{minor}\n'.format(major=MCGDB_VERSION.major,minor=MCGDB_VERSION.minor))
    gdb_print('python version: {major}.{minor}.{micor}\n'.format(major=sys.version_info.major,minor=sys.version_info.minor,micor=sys.version_info.micro))
    gdb_print('gdb version: {VERSION}\n'.format(VERSION=gdb.VERSION))
    gdb_print(get_prompt())
    gdb_rfd,gdb_wfd=os.pipe() #Through gdb_[rw]fd main pythread will be send commands to another thread
    self.gdb_wfd=gdb_wfd
    gdb.execute('set pagination off',False,False)
    gdb.execute('source {}'.format(PATH_TO_DEFINES_MCGDB))
    gethread = GEThread(gdb_rfd,main_thread_ident)
    with pysigset.suspended_signals(signal.SIGCHLD):
      event_thread=threading.Thread (target=gethread,args=()) #this thread will be communicate with editors
      event_thread.start()


    self.event_thread=event_thread

    #unused events commented
    #gdb.events.cont.connect(               self.notify_gdb_cont )
    gdb.events.exited.connect(             self.notify_gdb_exited )
    gdb.events.stop.connect(               self.notify_gdb_stop )
    gdb.events.new_objfile.connect(        self.notify_gdb_new_objfile )
    gdb.events.clear_objfiles.connect(      self.notify_gdb_clear_objfiles )
    #gdb.events.inferior_call_pre.connect(  self.notify_gdb_inferior_call_pre )
    #gdb.events.inferior_call_post.connect( self.notify_gdb_inferior_call_post )
    gdb.events.memory_changed.connect(     self.notify_gdb_memory_changed)
    gdb.events.register_changed.connect(   self.notify_gdb_register_changed)
    gdb.events.breakpoint_created.connect( self.notify_gdb_breakpoint_created  )
    gdb.events.breakpoint_deleted.connect( self.notify_gdb_breakpoint_deleted  )
    gdb.events.breakpoint_modified.connect(self.notify_gdb_breakpoint_modified )

    for win_name in ['src','aux','asm']:
      if win_name in WIN_LIST:
        self.open_window(win_name)


  def stop_event_loop(self):
    pkgsend(self.gdb_wfd,{'cmd':'stop_event_loop',})


  def notify_shellcmd(self,cmdname):
    if cmdname!='quit':
      pkgsend(self.gdb_wfd,{'cmd':'shellcmd','shellcmd':cmdname})
    else:
      pkgsend(self.gdb_wfd,{'cmd':'stop_event_loop'})

  def notify_gdbevt(self,evt,name):
    gdbevt_queue.append((name,evt))
    pkgsend(self.gdb_wfd,{'cmd':'gdbevt','gdbevt':name})

  def notify_gdb_cont (self, *evt):
    self.notify_gdbevt(evt,'cont')

  def notify_gdb_exited (self, *evt):
    self.notify_gdbevt(evt,'exited')

  def notify_gdb_stop (self, *evt):
    self.notify_gdbevt(evt,'stop')

  def notify_gdb_new_objfile (self, *evt):
    self.notify_gdbevt(evt,'new_objfile')

  def notify_gdb_clear_objfiles (self, *evt):
    self.notify_gdbevt(evt,'clear_objfiles')

  def notify_gdb_inferior_call_pre (self, *evt):
    self.notify_gdbevt(evt,'inferior_call_pre')

  def notify_gdb_inferior_call_post (self, *evt):
    self.notify_gdbevt(evt,'inferior_call_post')

  def notify_gdb_memory_changed (self, *evt):
    self.notify_gdbevt(evt,'memory_changed')

  def notify_gdb_register_changed (self, *evt):
    self.notify_gdbevt(evt,'register_changed')

  def notify_gdb_breakpoint_created (self, *evt):
    self.notify_gdbevt(evt,'breakpoint_created')

  def notify_gdb_breakpoint_deleted (self, *evt):
    self.notify_gdbevt(evt,'breakpoint_deleted')

  def notify_gdb_breakpoint_modified (self, *evt):
    self.notify_gdbevt(evt,'breakpoint_modified')

  def open_window(self,type, **kwargs):
    pkg={'cmd':'open_window','type':type}
    if 'manually' in kwargs:
      pkg['manually']=kwargs['manually']
    pkgsend(self.gdb_wfd,pkg)

class FrameFuncAddr(object):
  @exec_main
  def __init__(self,*args,**kwargs):
    super(FrameFuncAddr,self).__init__(*args,**kwargs)
    self.reg_disas_line_addr = re.compile('(=>)?\s+(0x[0-9a-fA-F]+)')

  @exec_main
  def get_function_block(self,frame):
    block=frame.block()
    while block:
      if block.function:
        return block
      block=block.superblock

  @exec_main
  def get_selected_frame_func(self):
    try:
      frame = gdb.selected_frame ()
    except gdb.error:
      return None,None,None
    if not frame:
      return None,None,None
    return self.get_frame_func(frame)

  @exec_main
  def get_frame_func(self,frame):
    try:
      block = self.get_function_block(frame)
      if block:
        start_addr,end_addr = block.start,block.end
      else:
        start_addr,end_addr = None,None
      return (frame.name(),start_addr,end_addr)
    except (RuntimeError,gdb.error,gdb.MemoryError):
      #for ex., if current frame corresponding
      #to malloc function, then selected_frame().block()
      #throw RuntimeError
      pc=frame.pc()
      try:
        res=gdb.execute('maintenance translate-address {addr}'.format(addr=pc),False,True)
        name = res.split()[0] #function name
      except gdb.error:
        name=None
      try:
        res=gdb.execute('disas {pc}'.format(pc=pc),False,True)
      except gdb.error, gdb.MemoryError:
        #error: No function contains specified address.
        return None,None,None
      lines=res.split('\n')
      first=lines[1]
      last=lines[-3]
      if self.reg_disas_line_addr.search(last)==None:
        gdbprint('WARNING: cant parse end addr of function')
        gdbprint(lines[-10:])
        return None,None,None
      start_addr = long(self.reg_disas_line_addr.search(first).groups()[1],0)
      end_addr = long(self.reg_disas_line_addr.search(last).groups()[1],0)
      return name,start_addr,end_addr

  def __call__(self,frame):
    return self.get_frame_func(frame)

frame_func_addr=FrameFuncAddr()
