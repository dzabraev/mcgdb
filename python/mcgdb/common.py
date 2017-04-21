#coding=utf8

import gdb
import sys,os,select,errno,socket,stat
import json
import logging
import threading, subprocess
import re,copy,ctypes


from mcgdb import PATH_TO_DEFINES_MCGDB
import mcgdb


main_thread_ident=threading.current_thread().ident
mcgdb_main=None


level = logging.CRITICAL
#level = logging.WARNING
#level = logging.DEBUG
logging.basicConfig(format = u'[%(module)s LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s', level = level)




class MCGDB_VERSION(object):
  major=1
  minor=1


def gdb_print(msg):
  gdb.post_event(lambda : gdb.write(msg))

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


def pkgsend(fd,msg):
  debug('SEND: {}'.format(str(msg)))
  jmsg=json.dumps(msg)
  smsg='{len};{data}'.format(len=len(jmsg),data=jmsg)
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


def exec_main(f):
  def decorated(*args,**kwargs):
    return exec_in_main_pythread (f,args,kwargs)
  return decorated

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

  def get_all_bps(self):
    ''' Возвращает все точки останова, которые есть в gdb'''
    return exec_in_main_pythread( gdb.breakpoints, ())

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

  def location_belongs_file(self,filename,line):
    if not filename or line==None:
      return False
    try:
      #check whether line belongs to file
      exec_in_main_pythread( gdb.decode_line, ('{}:{}'.format(filename,line),))
    except:
      #not belonging
      return False
    return True

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

  def get_bps_locs_normal(self,filename=None):
    normal_bps=[bp for bp in self.get_all_bps() if bp.enabled]
    return self.__bps_to_locs(normal_bps,filename)

  def get_bps_locs_disabled(self,filename=None):
    disabled_bps=[bp for bp in self.get_all_bps() if not bp.enabled]
    return self.__bps_to_locs(disabled_bps,filename)

  def get_bps_locs_wait_remove(self,filename=None):
    wait_remove_locs=[ param['bp'] for act,param in self.queue if act=='delete' ]
    return self.__bps_to_locs(wait_remove_locs, filename)

  def get_bps_locs_wait_insert(self,filename=None):
    wait_insert_locs=[ (param['filename'],param['line']) for act,param in self.queue if act=='insert' ]
    if filename!=None:
      return [ line for (fname,line) in wait_insert_locs ]
    else:
      return wait_insert_locs


  def __process(self):
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

  def process(self):
    ''' Данный метод пытается вставить/удалить точки останова 
        Если inferior запущен, то ничего сделано не будет
    '''
    exec_in_main_pythread(self.__process, () )


breakpoint_queue=BreakpointQueue()




def inferior_alive ():
  return not gdb.selected_thread()==None

def exec_in_main_pythread(func,args=(),kwargs={}):
  #Данную функцию нельзя вызывать более чем из одного потока
  if is_main_thread():
    return func(*args,**kwargs)
  result = {}
  evt=threading.Event()

  def exec_in_main_pythread_1(func,args,evt,result):
    try:
      result['retval']=func(*args)
      result['succ']='ok'
    except Exception:
      result['succ']='exception'
      result['except'] = sys.exc_info()
    evt.set()

  gdb.post_event(
      lambda : exec_in_main_pythread_1(func,args,evt,result)
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

  def __set_color(self,pkg):
    for fd in self.fte:
      win=self.fte[fd]
      win.set_color(pkg)

  def __process_pkg_from_gdb(self):
    pkg=pkgrecv(self.gdb_rfd)
    cmd=pkg['cmd']
    if cmd=='gdbevt':
      name,evt=gdbevt_queue.pop()
      for fd in self.fte:
        win=self.fte[fd]
        win.process_gdbevt(name,evt)
      breakpoint_queue.process()
    elif cmd=='shellcmd':
      cmdname=pkg['cmdname']
      for fd in self.fte:
        win=self.fte[fd]
        win.process_shellcmd(cmdname)
    ####mcgdb events
    elif   cmd=='open_window':
      self.__open_window(pkg)
    elif cmd=='color':
      self.__set_color(pkg)
    elif cmd=='stop_event_loop':
      for fd,win in self.fte.iteritems():
        win.terminate()
      sys.exit(0)
    else:
      debug('unrecognized package: `{}`'.format(pkg))
      return

  def __process_pkg_from_entity (self):
    pkg=self.entities_evt_queue.pop(0)
    gdb_print (pkg)
    cmd=pkg['cmd']
    if cmd=='check_breakpoint':
      breakpoint_queue.process()
    else:
      for fd in self.fte:
        entity=self.fte[fd]
        res = entity.process_pkg (pkg)
        if res:
          self.entities_evt_queue+=res


  def __call__(self):
    assert not self.WasCalled
    self.WasCalled=True
    self.entities_evt_queue=[] #Если при обработке пакета от editor или от чего-то еще
    #трубется оповестить другие окна о каком-то событии, то entity.process_pkg()
    #должен вернуть пакет(ы), которые будут обрабатываться в классах, которые соотв. окнам
    while True:
      if len(self.entities_evt_queue)>0:
        self.__process_pkg_from_entity ()
        continue
      rfds=self.fte.keys()
      rfds+=self.wait_connection.keys()
      rfds.append(self.gdb_rfd)
      try:
        fds=select.select(rfds,[],[])
      except select.error as se:
        if se[0]==errno.EINTR:
          continue
        else:
          raise
      ready_rfds=fds[0]
      for fd in ready_rfds:
        if fd==self.gdb_rfd:
          self.__process_pkg_from_gdb()
        elif fd in self.wait_connection.keys():
          entity=self.wait_connection[fd]
          ok=entity.process_connection()
          del self.wait_connection[fd]
          if ok:
            self.fte[entity.fd]=entity
            #entity.gdb_update_current_frame(self.exec_filename,self.exec_line)
        else:
          entity=self.fte[fd]
          try:
            res=entity.process_pkg ()
            if res:
              self.entities_evt_queue+=res
          except IOFailure:
            #возможно удаленное окно было закрыто =>
            #уничтожаем объект, который соответствует
            #потерянному окну.
            del self.fte[fd]
            debug('connection type={} was closed'.format(entity.type))
            entity.byemsg()
            entity=None #forgot reference to object
    debug('event_loop stopped\n')



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
      pkgsend(self.gdb_wfd,{'cmd':'shellcmd','cmdname':cmdname})
    else:
      pkgsend(self.gdb_wfd,{'cmd':'stop_event_loop'})

  def notify_gdbevt(self,evt,name):
    gdbevt_queue.append((name,evt))
    pkgsend(self.gdb_wfd,{'cmd':'gdbevt'})

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






