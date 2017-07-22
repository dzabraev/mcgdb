#coding=utf8

import gdb
import sys,os,select,errno,socket,stat,time
import signal
try:
  import pysigset
except:
  #sigset not exists in ubuntu repo; will distribute this package with mcgdb
  import mcgdb.deps.pysigset as pysigset
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

LOG_FILENAME='/tmp/mcgdb.log'

if 'DEBUG' in os.environ and os.path.exists(LOG_FILENAME):
  os.remove(LOG_FILENAME)

DEBUG = os.environ.get('DEBUG')
WITH_VALGRIND = os.environ.get('VALGRIND')

if 'debug' in os.environ or 'DEBUG' in os.environ:
  level = logging.INFO
  debug_messages=True
else:
  level = logging.CRITICAL
  debug_messages = False

logging.basicConfig(filename=LOG_FILENAME,format = u'[%(module)s LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s', level = level)

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

def exec_main(f):
  def decorated(*args,**kwargs):
    return exec_in_main_pythread (f,args,kwargs)
  return decorated


@exec_main
def if_gdbstopped_else(stopped=None,running=None):
  flag,cb = (True,stopped) if gdb_stopped() else (False,running)
  res = cb() if cb else None
  return flag,res


import mcgdb.gdb2 as gdb2



class MCGDB_VERSION(object):
  major=1
  minor=1

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

def stringify_value(value,**kwargs):
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
  enable_additional_text=kwargs.get('enable_additional_text',False)
  try:
    if type_code==gdb.TYPE_CODE_INT and kwargs.get('integer_mode') in ('dec','hex','bin') and value.type.strip_typedefs().sizeof<=8:
      mode=kwargs.get('integer_mode')
      bitsz=value.type.sizeof*8
      #gdb can't conver value to python-long if sizeof(value) > 8
      if mode=='dec':
        return str(long(value))
      elif mode=='hex':
        pattern='0x{{:0{hexlen}x}}'.format(hexlen=bitsz/4)
        return pattern.format(ctypes.c_ulong(long(value)).value)
      elif mode=='bin':
        pattern='{{:0{bitlen}b}}'.format(bitlen=bitsz)
        return pattern.format(ctypes.c_ulong(long(value)).value)
    if type_code in (gdb.TYPE_CODE_PTR,) and not enable_additional_text:
      return hex(ctypes.c_ulong(long(value)).value)[:-1]
    else:
      #например, если делать unicode или str для `.*char *`, то память будет читаться дважды.
      return unicode(value)
  except gdb.error:
    return "unavailable"

def stringify_value_safe(*args,**kwargs):
  try:
    return stringify_value(*args,**kwargs)
  except gdb.MemoryError:
    return 'Cannot access memory'




class GdbValueCache(object):
  def __init__(self):
    self.drop()

  def drop(self):
    ''' Drop all cache layers
    '''
    self.value_cache = {}
    self.value_str_cache = {}

  def cached_stringify_value(self,value,path,**kwargs):
    frnum=get_this_frame_num()
    if frnum==None:
      valcache=None
    else:
      key=(frnum,path)
      valcache=self.value_str_cache.get(key)
    if valcache==None:
      valcache=stringify_value_safe(value,**kwargs)
      self.value_str_cache[key]=valcache
    return valcache


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
cached_stringify_value = value_cache.cached_stringify_value
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
  if minor < good_minor:
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
  if level==logging.DEBUG:
    #эта блокировка нужна, поскольку exec_in_main_pythread
    #делает блокировки. И лучше их избегать.
    exec_in_main_pythread (logging.debug,(msg,))

def error(msg):
  exec_in_main_pythread (logging.error,(msg,))



def gdb_stopped_1():
  try:
    th=gdb.selected_thread()
    if th==None:
      return True
    return gdb.selected_thread().is_stopped()
  except:
    return True

def gdb_stopped():
  return exec_in_main_pythread(gdb_stopped_1)

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


class GdbBreakpoints(object):
  def __init__(self):
    pass

  @exec_main
  def get_all_bps(self):
    ''' Возвращает все точки останова, которые есть в gdb'''
    return gdb.breakpoints()

  def find_bp_in_gdb(self,filename,line):
    if not self.location_belongs_file(filename,line):
      return
    gdb_bps=self.get_all_bps()
    if gdb_bps!=None:
      try:
        return self.__find_bp_in_gdb_1(gdb_bps,filename,line)
      except gdb.error:
        return None
    else:
      return None

  def __find_bp_in_gdb_1(self,gdb_bps,filename,line):
    for bp in gdb_bps:
      if (filename,line) in self.get_bp_locations(bp):
        return bp
    return None

  @exec_main
  def location_belongs_file(self,filename,line):
    if not filename or line==None:
      return False
    try:
      #check whether line belongs to file
      gdb.decode_line('{}:{}'.format(filename,line),)
    except:
      #not belonging
      return False
    return True

  @exec_main
  def get_bp_locations(self,bp):
    if bp.type!=gdb.BP_BREAKPOINT:
      return []
    location=bp.location
    try:
      locs=exec_in_main_pythread(gdb.decode_line, (location,))[1]
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



class BreakpointQueue(GdbBreakpoints):
  ''' Очередь для уаления и создания точек останова .

      Если в отладчике inferior запущен, то в gdb нельзя
      вставлять и удалять точки сотанова. Нужно вставлять/удалять
      breakpoint через данный класс. Когда точки останова можно
      будет модифицировать, точки останова, добавленные в объект
      данного класса автоматически будут вставлены в gdb.
  '''

  def __init__(self):
    self.queue=[]

  def __find_bp_in_queue(self,filename,line):
    for idx in range(len(self.queue)):
      action,param = self.queue[idx]
      if   action=='insert':
        if param['filename']==filename and param['line']==line:
          return idx
      elif action=='delete':
        if (filename,line) in param['locations']:
          return idx
    return None

  @exec_main
  def insert_or_delete(self,filename,line):
    ''' Если bp существует, то данная bp удаляется. Если не существует, то дабавл.'''
    idx = self.__find_bp_in_queue(filename,line)
    if idx!=None:
      #Пока inferior работал пользователь нажал четное число
      #раз по точке останова. Просто удаляем ее.
      self.queue.pop(idx)
      return
    bp=self.find_bp_in_gdb(filename,line)
    if bp==None:
      #this bp not exists
      self.queue.append( ('insert',{
        'filename':filename,
        'line':line,
      }))
    else:
      self.queue.append( ('delete',{
        'bp':bp,
        'locations':self.get_bp_locations(bp),
      }))

  @exec_main
  def get_inserted_bps_locs(self,filename=None):
    ''' Данная функция возвращает список пар (fname,line) для каждой bp, которая либо уже
        вставлена в gdb и не находится в очереди на удаление, либо находится в
        очереди на вставку.

        Если задан необьязательный аргумент filename, то возвращаются только те пары,
        для которых fname==filename
    '''
    bps=self.get_all_bps()
    rmqueue=[ param['bp'] for act,param in self.queue if act=='delete' ]
    ok_bps=[bp for bp in bps if bp not in rmqueue]
    locs=[]
    wait_ins_locs=[ (param['filename'],param['line']) for act,param in self.queue if act=='insert' ]
    locs+=wait_ins_locs
    if filename:
      locs=[ (fname,line) for fname,line in locs if fname==filename]
    return locs

  def __bps_to_locs(self,bps,filename=None):
    locs=[]
    for bp in bps:
      locs += self.get_bp_locations(bp)
    if filename:
      locs=[ line for fname,line in locs if fname==filename ]
    return locs

  @exec_main
  def get_bps_locs_normal(self,filename=None):
    normal_bps=[bp for bp in self.get_all_bps() if bp.enabled]
    return self.__bps_to_locs(normal_bps,filename)

  @exec_main
  def get_bps_locs_disabled(self,filename=None):
    disabled_bps=[bp for bp in self.get_all_bps() if not bp.enabled]
    return self.__bps_to_locs(disabled_bps,filename)

  @exec_main
  def get_bps_locs_wait_remove(self,filename=None):
    wait_remove_locs=[ param['bp'] for act,param in self.queue if act=='delete' ]
    return self.__bps_to_locs(wait_remove_locs, filename)

  @exec_main
  def get_bps_locs_wait_insert(self,filename=None):
    wait_insert_locs=[ (param['filename'],param['line']) for act,param in self.queue if act=='insert' ]
    if filename!=None:
      return [ line for (fname,line) in wait_insert_locs ]
    else:
      return wait_insert_locs

  @exec_main
  def process(self):
    ''' Данный метод пытается вставить/удалить точки останова 
        Если inferior запущен, то ничего сделано не будет
    '''
    assert is_main_thread()
    if gdb.selected_thread()==None:
      #maybe inferior not running
      return
    if not gdb_stopped():
      #поток inferior'а исполняется. Точки ставить нельзя.
      return
    while len(self.queue)>0:
      action,param=self.queue.pop(0)
      if action=='insert':
        gdb.Breakpoint('{}:{}'.format(param['filename'],param['line']))
      elif action=='delete':
        param['bp'].delete()
      else:
        debug('unknown action: {}'.format(action))


breakpoint_queue=BreakpointQueue()



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
    if cmd=='check_breakpoint':
      breakpoint_queue.process()
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


  def __call__(self):
    assert not self.WasCalled
    self.WasCalled=True
    self.pending_pkgs=[] #Если target_running, а от gdb приходит event, например, new_objfile
    #и если при работающем target попытаться, например, обновить локальные переменные, то первое же
    #gdb.parse_and_eval() выбросит exception. Поэтому будем сохранять события от gdb пока не получим
    # 'exited' или 'stop'
    while True:
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
          entity=self.wait_connection[fd]
          try:
            ok=entity.process_connection()
            del self.wait_connection[fd]
          except OSError as e:
            gdb_print('Error while opening window: {}\n'.format(str(e)))
            ok=False
          if ok:
            self.fte[entity.fd]=entity
        else:
          entity_key,pkg=None,None
          if fd==self.gdb_rfd:
            #обработка пакета из gdb
            pkg = self.get_pkg_from_gdb()
          else:
            try:
              pkg = self.get_pkg_from_remote(fd)
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
        else:
          self.drop_pending_pkgs(lambda pkg:'gdbevt' in pkg and pkg['gdbevt']==cmd)
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

    self.open_window('src')
    self.open_window('aux')


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

  def notify_gdb_cont (self, evt):
    self.notify_gdbevt(evt,'cont')

  def notify_gdb_exited (self, evt):
    self.notify_gdbevt(evt,'exited')

  def notify_gdb_stop (self, evt):
    self.notify_gdbevt(evt,'stop')

  def notify_gdb_new_objfile (self, evt):
    self.notify_gdbevt(evt,'new_objfile')

  def notify_gdb_clear_objfiles (self, evt):
    self.notify_gdbevt(evt,'clear_objfiles')

  def notify_gdb_inferior_call_pre (self, evt):
    self.notify_gdbevt(evt,'inferior_call_pre')

  def notify_gdb_inferior_call_post (self, evt):
    self.notify_gdbevt(evt,'inferior_call_post')

  def notify_gdb_memory_changed (self, evt):
    self.notify_gdbevt(evt,'memory_changed')

  def notify_gdb_register_changed (self, evt):
    self.notify_gdbevt(evt,'register_changed')

  def notify_gdb_breakpoint_created (self, evt):
    self.notify_gdbevt(evt,'breakpoint_created')

  def notify_gdb_breakpoint_deleted (self, evt):
    self.notify_gdbevt(evt,'breakpoint_deleted')

  def notify_gdb_breakpoint_modified (self, evt):
    self.notify_gdbevt(evt,'breakpoint_modified')

  def open_window(self,type, **kwargs):
    pkg={'cmd':'open_window','type':type}
    if 'manually' in kwargs:
      pkg['manually']=kwargs['manually']
    pkgsend(self.gdb_wfd,pkg)
  def __send_color(self,name,text_color,background_color,attrs):
    pkg={
      'cmd':'color',
      name : {
        'background_color':background_color,
        'text_color': text_color,
      },
    }
    if attrs!=None:
      pkg[name]['attrs']=attrs
    pkgsend(self.gdb_wfd,pkg)
  def set_color_curline(self,text_color,background_color,attr):
    self.__send_color ('color_curline',text_color,background_color,attr)
  def set_color_bp_normal(self,text_color,background_color,attr):
    self.__send_color ('color_bp_normal',text_color,background_color,attr)
  def set_color_bp_disabled(self,text_color,background_color,attr):
    self.__send_color ('color_bp_disabled',text_color,background_color,attr)
  def set_color_bp_wait_remove(self,text_color,background_color,attr):
    self.__send_color ('color_bp_wait_remove',text_color,background_color,attr)
  def set_color_bp_wait_insert(self,text_color,background_color,attr):
    self.__send_color ('color_bp_wait_insert',text_color,background_color,attr)



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
    except (RuntimeError,gdb.error):
      #for ex., if current frame corresponding
      #to malloc function, then selected_frame().block()
      #throw RuntimeError
      pc=frame.pc()
      res=gdb.execute('maintenance translate-address {addr}'.format(addr=pc),False,True)
      name = res.split()[0] #function name
      res=gdb.execute('disas {pc}'.format(pc=pc),False,True)
      lines=res.split('\n')
      first=lines[1]
      last=lines[-3]
      start_addr = long(self.reg_disas_line_addr.search(first).groups()[1],0)
      end_addr = long(self.reg_disas_line_addr.search(last).groups()[1],0)
      return name,start_addr,end_addr

  def __call__(self,frame):
    return self.get_frame_func(frame)

frame_func_addr=FrameFuncAddr()
