#coding=utf8

from abc import ABCMeta, abstractmethod, abstractproperty
import sys,os,select,errno,socket,stat
import json
import logging
import threading
import re

import gdb

logging.basicConfig(format = u'[%(module)s LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s', level = logging.DEBUG)

PATH_TO_MC="/home/dza/bin/mcedit"
PATH_TO_DEFINES_MCGDB="~/bin/defines-mcgdb.gdb"
TMP_FILE_NAME="/tmp/mcgdb-tmp-file-{pid}.txt".format(pid=os.getpid())
main_thread_ident=threading.current_thread().ident


class CommandReadFailure(Exception): pass

def debug(msg):
  exec_in_main_pythread (logging.debug,(msg,))

def gdb_print(msg):
  gdb.post_event(lambda : gdb.write(msg))

def exec_cmd_in_gdb(cmd):
  try:
    exec_in_main_pythread( gdb.execute, (cmd,False) )
  except gdb.error:
    pass


def pkgsend(fd,msg):
  gdb_print(str(msg)+'\n')
  jmsg=json.dumps(msg)
  smsg='{len};{data}'.format(len=len(jmsg),data=jmsg)
  n=0
  total=len(smsg)
  while n<total:
    n+=os.write(fd,smsg[n:])

def pkgrecv(fd):
  lstr=''
  b=os.read(fd,1)
  while b!=';':
    lstr+=b
    try:
      b=os.read(fd,1)
    except IOError as e:
      if e.errno == errno.EINTR:
        continue
      else:
        raise
    if len(b)==0:
      raise CommandReadFailure
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
    if len(data1)==0:
      raise CommandReadFailure
    nrecv+=len(data1)
    data+=data1
  return json.loads(data)



def is_main_thread():
  return threading.current_thread().ident==main_thread_ident


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
    locs=exec_in_main_pythread(gdb.decode_line, (location,))[1]
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
      вставлять и удалять точки сотанова. Вставлять/удалять
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
    for bp in ok_bps:
      locs += self.get_bp_locations(bp)
    wait_ins_locs=[ (param['filename'],param['line']) for act,param in self.queue if act=='insert' ]
    locs+=wait_ins_locs
    if filename:
      locs=[ (filename,line) for filename,line in locs if filename==filename]
    return locs

  def __process(self):
    assert is_main_thread()
    if gdb.selected_thread()==None:
      #maybe inferior not running
      return
    if not gdb.selected_thread().is_stopped():
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


def exec_in_main_pythread(func,args):
  #Данную функцию нельзя вызывать более чем из одного потока
  if is_main_thread():
    return func(*args)
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









class BaseWindow(object):

  def __init__(self):
    lsock=socket.socket()
    lsock.bind( ('',0) )
    lsock.listen(1)
    lport=lsock.getsockname()[1]
    os.system('gnome-terminal -e "{path_to_mc} -e --gdb-port={gdb_port}"'.format(
      path_to_mc=PATH_TO_MC,gdb_port=lport))
    conn = lsock.accept()[0]
    lsock.close()
    self.fd=conn.fileno()
    self.conn=conn
    pkgsend(self.fd,{
      'cmd' :'set_window_type',
      'type':self.type,
    })

  @abstractproperty
  def type(self):
    pass

  def send(self,msg):
    pkgsend(self.fd,msg)

  def recv(self):
    return pkgrecv(self.fd)

class MainWindow(BaseWindow):

  type='main_window'
  startcmd='mcgdb mainwindow'

  def __init__(self):
    super(MainWindow,self).__init__()
    self.editor_cbs = {
      'editor_breakpoint'       :  self. __editor_breakpoint,
      'editor_breakpoint_de'    :  self. __editor_breakpoint_de,
      'editor_next'             :  self. __editor_next,
      'editor_step'             :  self. __editor_step,
      'editor_until'            :  self. __editor_until,
      'editor_continue'         :  self. __editor_continue,
    }
    self.exec_filename=None #текущему фрейму соответствует это имя файла исзодного кода
    self.exec_line=None     #номер строки текущего исполнения
    self.edit_filename=None #Файл, который открыт в редакторе. Если исходник открыть нельзя, то
                            #открывается файл-заглушка
    self.gdb_check_breakpoint()


  def byemsg(self):
    gdb_print("type `{cmd}` to restart {type}\n".format(cmd=self.startcmd,type=self.type))

  def gdb_inferior_stop(self):
    pass
  def gdb_inferior_exited(self):
    pass
  def gdb_new_objfile(self):
    pass
  def gdb_update_current_frame(self,filename,line):
    '''Данная функция извлекает из gdb текущий файл
        и номер строки исполнения. После чего, если необходимо, открывает
        файл с исходником в редакторе и перемещает экран к линии исполнения.
    '''
    if (not filename and self.edit_filename!=TMP_FILE_NAME) or filename!=self.exec_filename:
      if self.edit_filename:
        #если в редакторе был открыт файл, то закрываем его.
        self.send({'cmd':'fclose'})
      if not filename or not os.path.exists(filename) or \
        not ( os.stat(filename).st_mode & stat.S_IFREG and \
              os.stat(filename).st_mode & stat.S_IREAD \
        ):
        #новый файл неизвестен, либо не существует, либо не является файлом.
        #открываем в редакторе заглушку
        with open(TMP_FILE_NAME,'w') as f:
          if not filename:
            f.write('\nCurrent execution position and source file not known.\n')
          else:
            f.write('\nFilename {} not exists\n'.format(filename))
        self.send({
          'cmd'       :   'fopen',
          'filename'  :   TMP_FILE_NAME,
          'line'      :   1,
        })
        self.edit_filename=TMP_FILE_NAME
      else:
        #все нормально, файл существует, его можно прочитать
        self.send({
          'cmd'       :   'fopen',
          'filename'  :   filename,
          'line'      :   line if line!=None else 0,
        })
        self.edit_filename=filename
    if line!=self.exec_line and line!=None:
      self.send({'cmd':'set_curline',  'line':line})
    self.exec_filename=filename
    self.exec_line=line


  def gdb_check_breakpoint(self):
    pass

  #commands from editor
  def __editor_breakpoint(self,pkg):
    line=pkg['line']
    if self.edit_filename==TMP_FILE_NAME:
      #в редакторе открыт файл-заглушка.
      #молча игнорируем попытки манипуляцией брейкпоинтами
      return
    breakpoint_queue.insert_or_delete(self.edit_filename,line)
    breakpoint_queue.process()
  def __editor_breakpoint_de(self,pkg):
    ''' Disable/enable breakpoint'''
    raise NotImplementedError
    breakpoint_queue.process()
  def __editor_next(self,pkg):
    exec_cmd_in_gdb("next")
  def __editor_step(self,pkg):
    exec_cmd_in_gdb("step")
  def __editor_until(self,pkg):
    exec_cmd_in_gdb("until")
  def __editor_continue(self,pkg):
    exec_cmd_in_gdb("continue")


  def process_pkg(self):
    '''Обработать сообщение из редактора'''
    pkg=self.recv()
    cmd=pkg['cmd']
    return self.editor_cbs[cmd](pkg)




class GEThread(object):
  def __init__(self,gdb_rfd,main_thread_ident):
    self.gdb_rfd=gdb_rfd
    self.main_thread_ident=main_thread_ident
    self.fte={}
    self.WasCalled=False
    self.exec_filename=None
    self.exec_line=None

  def __get_current_position_main_thread(self):
    assert is_main_thread()
    #Данную функцию можно вызывать только из main pythread или
    #через функцию exec_in_main_pythread
    try:
      frame=gdb.selected_frame ()
      #filename=frame.find_sal().symtab.filename
      #filename=get_abspath(filename)
      filename=frame.find_sal().symtab.fullname()
      line=frame.find_sal().line-1
    except: #gdb.error:
      #no frame selected or maybe inferior exited?
      filename=None
      line=None
    return filename,line

  def __get_current_position(self):
    return exec_in_main_pythread(
          self.__get_current_position_main_thread,())

  def __update_current_position_in_win(self):
    filename,line = self.__get_current_position()
    if (not filename or filename!=self.exec_filename) or \
       (not line or line!=self.exec_line):
      for fd in self.fte:
        win=self.fte[fd]
        if win.type in ('main_window','source_window'):
          win.gdb_update_current_frame(filename,line)
      self.exec_filename=filename
      self.exec_line=line

  def __open_window(self, pkg):
    type=pkg['type']
    if type=='main_window':
      window=MainWindow()
    else:
      debug('bad `type`: `{}`'.format(pkg))
      return
    self.fte[window.fd] = window
    window.gdb_update_current_frame(self.exec_filename,self.exec_line)

  def __check_breakpoint(self):
    pass

  def __process_pkg_from_gdb(self):
    pkg=pkgrecv(self.gdb_rfd)
    cmd=pkg['cmd']
    if   cmd=='open_window':
      self.__open_window(pkg)
    elif cmd=='stop_event_loop':
      sys.exit(0)
    elif cmd=='check_frame':
      self.__update_current_position_in_win()
      breakpoint_queue.process()
    elif cmd=='inferior_stop':
      self.__update_current_position_in_win()
      breakpoint_queue.process()
    elif cmd=='new_objfile':
      self.__update_current_position_in_win()
      breakpoint_queue.process()
    elif cmd=='check_breakpoint':
      self.__check_breakpoint()
      breakpoint_queue.process()
    elif cmd=='inferior_exited':
      self.__update_current_position_in_win()
      breakpoint_queue.process()
    else:
      debug('unrecognized package: `{}`'.format(pkg))
      return

  def __call__(self):
    assert not self.WasCalled
    self.WasCalled=True
    while True:
      rfds=self.fte.keys()
      rfds.append(self.gdb_rfd)
      timeout=0.1
      #timeout ставится чтобы проверять, нужно ли останавливать этот цикл
      try:
        fds=select.select(rfds,[],[],timeout)
      except select.error as se:
        if se[0]==errno.EINTR:
          continue
        else:
          raise
      ready_rfds=fds[0]
      for fd in ready_rfds:
        if fd==self.gdb_rfd:
          self.__process_pkg_from_gdb()
        else:
          entity=self.fte[fd]
          try:
            entity.process_pkg ()
          except CommandReadFailure:
            #возможно удаленное окно было закрыто =>
            #уничтожаем объект, который соответствует
            #потерянному окну.
            del self.fte[fd]
            debug('connection type={} was closed'.format(entity.type))
            entity.byemsg()
            entity=None #forgot reference to object
    gdb_print('event_loop stopped\n')



class McgdbMain(object):
  def __init__(self):
  #global event_thread,gdb_listen_port,   main_thread_ident,mcgdb_initialized
    if not self.__is_gdb_version_correct():
      return
    gdb_rfd,gdb_wfd=os.pipe() #Through gdb_[rw]fd main pythread will be send commands to another thread
    self.gdb_wfd=gdb_wfd
    gdb.execute('set pagination off',False,False)
    gdb.execute('source {}'.format(PATH_TO_DEFINES_MCGDB))
    gethread = GEThread(gdb_rfd,main_thread_ident)
    event_thread=threading.Thread (target=gethread,args=()) #this thread will be communicate with editors
    event_thread.start()

    gdb.events.stop.connect( self.notify_inferior_stop )
    gdb.events.exited.connect( self.notify_inferior_exited )
    gdb.events.new_objfile.connect( self.notify_new_objfile )
    gdb.events.breakpoint_created.connect( self.notify_breakpoint )
    gdb.events.breakpoint_deleted.connect( self.notify_breakpoint )

    self.open_window('main_window')

  def __get_gdb_version(self):
    try:
      s=gdb.execute('show version',False,True)
      major,minor=re.compile(r"GNU gdb \(GDB\) (\d+).(\d+)",re.MULTILINE).search(s).groups()
      ver=(int(major),int(minor))
      return ver
    except:
      return (None,None)


  def __is_gdb_version_correct(self):
    good_major=7
    good_minor=12
    major,minor=self.__get_gdb_version()
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

  def stop_event_loop(self):
    pkgsend(self.gdb_wfd,{'cmd':'stop_event_loop',})

  def notify_inferior_stop(self,x):
    pkgsend(self.gdb_wfd,{'cmd':'inferior_stop',})
  def notify_inferior_exited(self,exit_code):
    pkgsend(self.gdb_wfd,{'cmd':'inferior_exited',})
  def notify_new_objfile(self,x):
    pkgsend(self.gdb_wfd,{'cmd':'new_objfile',})
  def notify_check_frame(self):
    pkgsend(self.gdb_wfd,{'cmd':'check_frame',})
  def notify_breakpoint(self,x):
    pkgsend(self.gdb_wfd,{'cmd':'check_breakpoint',})
  def open_window(self,type):
    pkgsend(self.gdb_wfd,{'cmd':'open_window','type':type})

#mcgdb_main=McgdbMain()

