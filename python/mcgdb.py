#coding=utf8

from abc import ABCMeta, abstractmethod, abstractproperty
import sys,os,select,errno,socket,stat
import json
import logging
import threading, subprocess
import re,copy,ctypes

import gdb

#NOTES
# PATH_TO_DEFINES_MCGDB and PATH_TO_MC defined in python/mcgdb_const.py

level = logging.CRITICAL
#level = logging.WARNING
#level = logging.DEBUG
logging.basicConfig(format = u'[%(module)s LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s', level = level)

debug_wins={}

TMP_FILE_NAME="/tmp/mcgdb/mcgdb-tmp-file-{pid}.txt".format(pid=os.getpid())
main_thread_ident=threading.current_thread().ident
mcgdb_main=None

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

class IOFailure(Exception): pass

def debug(msg):
  if level==logging.DEBUG:
    #эта блокировка нужна, поскольку exec_in_main_pythread
    #делает блокировки. И лучше их избегать.
    exec_in_main_pythread (logging.debug,(msg,))

def error(msg):
  exec_in_main_pythread (logging.error,(msg,))


def gdb_print(msg):
  gdb.post_event(lambda : gdb.write(msg))

def get_prompt():
  res=exec_in_main_pythread( gdb.execute, ('show prompt',False,True) )
  regex=re.compile('''Gdb's prompt is "([^"]+)".''')
  prompt=regex.match(res).groups()[0]
  return prompt

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
#    exec_in_main_pythread(
#      gdb.execute, ('echo {prompt}\ '.format(prompt=get_prompt()),False) )
  except gdb.error:
    pass


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

def exec_in_main_pythread(func,args=()):
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




def check_chunks(chunks):
  if type(chunks) not in (dict,list):
    gdb_print ('bad chunks: `{}`\n'.format(chunks))
    return
  if type(chunks) is dict:
    if 'str' in chunks:
      return
    elif 'chunks' in chunks:
      check_chunks(chunks['chunks'])
    else:
      gdb_print ('bad chunks: {}'.format(chunks))
      return
  else:
    for child in chunks:
      check_chunks(child)




class BaseWindow(object):

  def __init__(self, **kwargs):
    '''
        Args:
            **manually (bool): Если false, то команда для запуска граф. окна не будет выполняться.
                Вместе этого пользователю будет выведена команда, при помощи которой он сам должен
                запустить окно. Данную опцию нужно применять, когда нет возможности запустить граф. окно
                из gdb. Например, если зайти по ssh на удаленную машину, то не всегда есть возможность
                запустить gnome-terminal.
    '''
    if not hasattr(self,'window_event_handlers'):
      self.window_event_handlers={}
    self.window_event_handlers.update({
      'editor_next'             :  self._editor_next,
      'editor_step'             :  self._editor_step,
      'editor_until'            :  self._editor_until,
      'editor_continue'         :  self._editor_continue,
      'editor_frame_up'         :  self._editor_frame_up,
      'editor_frame_down'       :  self._editor_frame_down,
      'editor_finish'           :  self._editor_finish,
    })

    debug_wins[self.type]=self #debug
    if os.path.exists(os.path.abspath('~/tmp/mcgdb-debug/core')):
      os.remove(os.path.abspath('~/tmp/mcgdb-debug/core'))
    #self.gui_window_cmd='''gnome-terminal -e 'bash -c "cd ~/tmp/mcgdb-debug/; touch 1; ulimit -c unlimited; {cmd}"' '''
    #self.gui_window_cmd='''gnome-terminal -e 'valgrind --log-file=/tmp/vlg.log {cmd}' '''
    self.gui_window_cmd='''gnome-terminal -e '{cmd}' '''
    self.lsock=socket.socket()
    self.lsock.bind( ('',0) )
    self.lsock.listen(1)
    self.listen_port=self.lsock.getsockname()[1]
    self.listen_fd=self.lsock.fileno()
    manually=kwargs.get('manually',False)
    cmd=self.make_runwin_cmd()
    complete_cmd=self.gui_window_cmd.format(cmd=cmd)
    if manually:
      gdb_print('''Execute manually `{cmd}` for start window'''.format(cmd=cmd))
    else:
      proc=subprocess.Popen(complete_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      proc.wait()
      rc=proc.returncode
      if rc!=0:
        out,err = proc.communicate()
        error('''command: `{complete_cmd}` return error code: {rc}.
You can try execute this command manually from another terminal.
stdout=`{stdout}`\nstderr=`{stderr}`'''.format(
  complete_cmd=complete_cmd,rc=rc,stdout=out,stderr=err))
        gdb_print('''Can't open gui window. execute manually: `{cmd}`'''.format(cmd=cmd))

  def _editor_next(self,pkg):
    if gdb_stopped():
      exec_cmd_in_gdb("next")
  def _editor_step(self,pkg):
    if gdb_stopped():
      exec_cmd_in_gdb("step")
  def _editor_until(self,pkg):
    if gdb_stopped():
      exec_cmd_in_gdb("until")
  def _editor_continue(self,pkg):
    if gdb_stopped():
      exec_cmd_in_gdb("continue")
  def _editor_frame_up(self,pkg):
    if gdb_stopped():
      exec_cmd_in_gdb("up")
  def _editor_frame_down(self,pkg):
    if gdb_stopped():
      exec_cmd_in_gdb("down")
  def _editor_finish(self,pkg):
    if gdb_stopped():
      exec_cmd_in_gdb("finish")

  def make_runwin_cmd(self):
    ''' Данный метод формирует shell-команду для запуска окна с editor.
        Команда формируется на основе self.listen_port
    '''
    return '{path_to_mc} -e --gdb-port={gdb_port}'.format(
     path_to_mc=PATH_TO_MC,gdb_port=self.listen_port)


  def byemsg(self):
    gdb_print("type `{cmd}` to restart {type}\n{prompt}".format(
      cmd=self.startcmd,type=self.type,prompt=get_prompt()))


  def process_connection(self):
    self.conn = self.lsock.accept()[0]
    self.lsock.close()
    self.lsock      =None
    self.listen_port=None
    self.listen_fd  =None
    self.fd=self.conn.fileno()
    pkgsend(self.fd,{
      'cmd' :'set_window_type',
      'type':self.type,
    })
    return True

  @abstractproperty
  def runwindow_cmd(self):
    pass

  @abstractproperty
  def type(self):
    pass

  def send(self,msg):
    pkgsend(self.fd,msg)

  def recv(self):
    return pkgrecv(self.fd)

  def process_pkg(self,pkg=None):
    '''Обработать сообщение из графического окна или от другой сущности'''
    if pkg==None:
      pkg=self.recv()
    cmd=pkg['cmd']
    if cmd=='shellcmd':
      cmdname=pkg['cmdname']
      self.process_shellcmd(cmdname)
    else:
      cb=self.window_event_handlers.get(cmd)
      if cb==None:
        debug("unknown `cmd`: `{}`".format(pkg))
      else:
        return cb(pkg)

  def terminate(self):
    try:
      self.send({'cmd':'exit'})
    except:
      pass

  def __get_current_position_1(self):
    assert is_main_thread()
    #Данную функцию можно вызывать только из main pythread или
    #через функцию exec_in_main_pythread
    try:
      frame=gdb.selected_frame ()
      filename=frame.find_sal().symtab.fullname()
      line=frame.find_sal().line-1
    except: #gdb.error:
      #no frame selected or maybe inferior exited?
      filename=None
      line=None
    return filename,line

  def get_current_position(self):
    '''Возвращает текущую позицию исполнения.

        return:
        (filename,line)
    '''
    return exec_in_main_pythread(self.__get_current_position_1,())

  def send_error(self,message):
    try:
      self.send({'cmd':'error_message','message':message})
    except:
      pass


def is_incomplete_type_ptr(value):
  return  value.type.strip_typedefs().code==gdb.TYPE_CODE_PTR and \
          value.type.strip_typedefs().target().strip_typedefs().code in (gdb.TYPE_CODE_STRUCT,gdb.TYPE_CODE_UNION) and \
          len(value.type.target().strip_typedefs().fields())==0

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
  if type_code==gdb.TYPE_CODE_INT and kwargs.get('integer_as_hex') and value.type.sizeof<=8:
    #gdb can't conver value to python-long if sizeof(value) > 8
    return hex(long(value))[:-1]
  if type_code in (gdb.TYPE_CODE_PTR,) and not enable_additional_text:
    return hex(ctypes.c_ulong(long(value)).value)[:-1]
  else:
    return unicode(value)

def stringify_value_safe(*args,**kwargs):
  try:
    return stringify_value(*args,**kwargs)
  except gdb.MemoryError:
    return 'Cannot access memory'


class LocalVarsWindow(BaseWindow):
  ''' Representation of window with localvars of current frame
  '''

  type='localvars_window'
  startcmd='mcgdb open localvars'

  def __init__(self, **kwargs):
    super(LocalVarsWindow,self).__init__(**kwargs)
    self.window_event_handlers.update({
      'onclick_data'    : self._onclick_data,
    })
    self.click_cmd_cbs={
      'select_frame'    : self._select_frame,
      'select_thread'   : self._select_thread,
      'change_variable' : self._change_variable,
      'change_slice'    : self._change_slice,
      'expand_variable' : self._expand_variable,
      'collapse_variable':self._collapse_variable,
    }
    self.regex_split = re.compile('\s*([^\s]+)\s+([^\s+]+)\s+(.*)')
    #self.slice_type_1=re.compile('^\s*(\d+)\s*$')
    #self.slice_type_2=re.compile('^\s*(\d+)[:, ](\d+)\s*$')
    self.slice_regex=re.compile('^(-?\d+)([:, ](-?\d+))?$')

    self.regnames=[]
    self.user_slice={}
    self.expand_variable={}
    regtab = gdb.execute('maint print registers',False,True).split('\n')[1:]
    for reg in regtab:
      if reg=="*1: Register type's name NULL.":
        continue
      reg=reg.split()
      if len(reg)>0 and reg[0] and reg[0]!="''" and len(reg[0])>0:
        self.regnames.append('$'+reg[0])

  def process_connection(self):
    rc=super(LocalVarsWindow,self).process_connection()
    if rc:
      self.update_all()
    return rc


  def _onclick_data(self,pkg):
    #gdb_print(str(pkg)+'\n')
    click_cmd = pkg['data']['click_cmd']
    cb=self.click_cmd_cbs.get(click_cmd)
    if cb==None:
      return
    return cb(pkg)

  def _expand_variable(self,pkg):
    path=pkg['data']['path']
    funcname=pkg['data']['funcname']
    self.expand_variable[(funcname,path)]=True
    self.update_all()

  def _collapse_variable(self,pkg):
    path=pkg['data']['path']
    funcname=pkg['data']['funcname']
    self.expand_variable[(funcname,path)]=False
    self.update_all()



  def _change_slice_1(self,pkg):
    path=pkg['data']['path']
    funcname=pkg['data']['funcname']
    user_input = pkg['user_input']
    match=self.slice_regex.match(user_input)
    if match:
      grps=match.groups()
      n1=int(grps[0])
      if grps[2]!=None:
        n2=int(grps[2])
      else:
        n2=None
      if n2!=None and n1>=n2:
        self.send_error('bad input: right bound must be greater than left')
        return
      self.user_slice[(funcname,path)] = (n1,n2)
    else:
      self.send_error('bad input: {}'.format(user_input))
      return
    self.update_localvars()
    self.update_backtrace()

  def _change_slice(self,pkg):
    return self._change_slice_1(pkg)

  def _change_variable_1(self,pkg):
    if not gdb_stopped():
      self.send_error('inferior running')
      return None
    if not inferior_alive ():
      self.send_error('inferior not alive')
      return None
    path=pkg['data']['path']
    user_input = pkg['user_input']
    value=gdb.parse_and_eval(path)
    if value.type.strip_typedefs().code in (gdb.TYPE_CODE_INT,gdb.TYPE_CODE_PTR):
      try:
        new_value=long(gdb.parse_and_eval(user_input))
      except Exception as e:
        self.send_error(str(e))
        return None
    else:
      new_value = user_input
    gdb_cmd='set variable {path}={new_value}'.format(path=path,new_value=new_value)
    try:
      exec_in_main_pythread(gdb.execute, (gdb_cmd,))
    except Exception as e:
      self.send_error(str(e))
      return None
    self.update_all()

  def _change_variable(self,pkg):
    return exec_in_main_pythread(self._change_variable_1, (pkg,))


  def _select_thread_1(self,nthread):
    threads=gdb.selected_inferior().threads()
    if len(threads)<nthread+1:
      return 'thread #{} not exists'.format(nthread)
    threads[nthread].switch()
    self.update_all()

  def _select_thread(self,pkg):
    nthread = pkg['data']['nthread']
    res=exec_in_main_pythread(self._select_thread_1, (nthread,))
    if res!=None:
      self.send_error(res)
    else:
      # эмитируем, что пользователь вызвал в шелле команду, и оповещаем
      # об этом остальные сущности
      return [{'cmd':'shellcmd','cmdname':'thread'}]

  def _select_frame_1(self,nframe):
    if not gdb_stopped():
      return 'inferior running'
    if not inferior_alive ():
      return 'inferior not alive'
    n_cur_frame=0
    frame = gdb.newest_frame ()
    while frame:
      if n_cur_frame==nframe:
        frame.select()
        self.update_all()
        return
      n_cur_frame+=1
      frame = frame.older()
    return "can't find frame #{}".format(nframe)

  def _select_frame(self,pkg):
    nframe = pkg['data']['nframe']
    res=exec_in_main_pythread(self._select_frame_1, (nframe,))
    if res!=None:
      self.send_error(res)
    else:
      return [{'cmd':'shellcmd','cmdname':'frame'}]


  def gdb_inferior_stop(self):
    pass
  def gdb_inferior_exited(self):
    pass
  def gdb_new_objfile(self):
    pass
  def gdb_update_current_frame(self,filename,line):
    pass

  def update_localvars(self):
    lvars=self._get_local_vars()
    pkg={'cmd':'localvars','table':lvars}
    self.send(pkg)

  def update_backtrace(self):
    try:
      backtrace = self.get_stack()
    except gdb.error:
      return
    pkg={
      'cmd':'backtrace',
      'table':backtrace,
    }
    self.send(pkg)
  def update_registers(self):
    try:
      regs = self.get_registers()
    except gdb.error as e:
      if e.message=="No registers.":
        return
      else:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        raise exc_type, exc_value, exc_traceback
    pkg={
      'cmd':'registers',
      'table':regs,
    }
    self.send(pkg)
  def update_threads(self):
    try:
      self.send({
        'cmd':'threads',
        'table':self.get_threads(),
      })
    except:
      return
  def gdb_check_breakpoint(self):
    pass
  def set_color(self,pkg):
    pass

  def _get_local_vars(self):
    #try:
    res=exec_in_main_pythread( self._get_local_vars_chunks, ())
    #except (gdb.error,RuntimeError):
      #import traceback
      #traceback.print_exc()
    #  res=[]
    return res

  def make_subarray_name(self,value,valuepath,**kwargs):
    funcname = kwargs.get('funcname')
    n1,n2=self.user_slice.get((funcname,valuepath),(0,2))
    chunks = [{'str':'*(','name':'varname'}]+\
    self.changable_value_to_chunks(value,valuepath,**kwargs)+\
    [{'str':')','name':'varname'}]+\
    [self.make_slice_chunk(n1,n2,valuepath,funcname)]
    return chunks

  def array_to_chunks (self, value, name, n1, n2, path, deref_depth, **kwargs):
    ''' Конвертация массива или указателя, который указывает на массив в json-дерево.

        Args:
          n1 (int): Начиная с этого номера элементы массива будут напечатаны.
          n2 (int): включительно по этот номер будут напечатаны элементы массива.

        Если элементы массива не указатели, то печатается нечто вроде
        arr = [p1,p2,..,pn]
        Если элементы массива есть указатели, тип которых не "char *"
        и не "void *", то печатается конструкция вида
        arr = [
           *(p1) = [...]
           *(p2) = [...]
        ]
        Где p1,p2 есть адреса, а конструкция между  [...] есть содержимое указателя

    '''
    chunks=[]
    assert name!=None
    assert path
    funcname=kwargs.get('funcname')
    already_deref=kwargs.get('already_deref')
    arrloc=(funcname,path)

    type_code=value.type.strip_typedefs().code
    if name:
      chunks+=self.value_type_to_chunks(value,**kwargs)
      chunks.append({'str':' '})

    if type(name) is str:
      slice_chunk = self.make_slice_chunk(n1,n2,path,funcname)
      varname=[
        {'str':name,'name':'varname'},
        slice_chunk,
      ]
      chunks+=varname
    else:
      chunks+=name
    chunks+=[{'str':' = '}]
    valueloc=(funcname,path)
    if type_code==gdb.TYPE_CODE_PTR:
      value_addr = ctypes.c_ulong(long(value)).value
    else:
      try:
        value_addr = value.address
      except gdb.MemoryError:
        value_addr=None
    is_already_deref = value_addr!=None and value_addr in already_deref
    if ((deref_depth>=kwargs.get('max_deref_depth',3) or is_already_deref) and not self.expand_variable.get((funcname,path))) or \
        (valueloc in self.expand_variable and not self.expand_variable[(funcname,path)] ):
      chunks += self.collapsed_array_to_chunks(path,**kwargs)
      return chunks

    if value_addr!=None:
      already_deref.add(value_addr)

    chunks1=[]
    array_data_chunks=[]
    n22 = n2+1 if n2!=None else n1+1
    deref_value = value[n1]
    deref_type_code = deref_value.type.strip_typedefs().code
    deref_type_str  = str(deref_value.type.strip_typedefs())
    if deref_type_code==gdb.TYPE_CODE_PTR and not re.match('.*((char \*)|(void \*))$',deref_type_str) and not is_incomplete_type_ptr(deref_value):
      name_lambda = lambda value,valuepath,**kwargs : self.make_subarray_name(value,valuepath,**kwargs)
      elem_as_array=True
    else:
      name_lambda = lambda value,valuepath,**kwargs : None
      elem_as_array=False

    arr_elem_size=deref_value.type.sizeof
    arr_size=n2-n1+1 if n2!=None else 1
    if value_addr==None or self.possible_read_memory(value_addr,arr_elem_size*arr_size):
      if 'delimiter' in kwargs:
        delimiter=kwargs['delimiter']
      else:
        if deref_type_code in (gdb.TYPE_CODE_INT,gdb.TYPE_CODE_FLT):
          delimiter={'str':', '}
        else:
          delimiter={'str':',\n'}
      for i in range(n1,n22):
        path_idx = '{path}[{idx}]'.format(path=path,idx=i)
        try:
          value_idx = value[i]
          value_idx_name = name_lambda(value_idx,path_idx,**kwargs)
        except gdb.MemoryError:
          memory_error_idx=i
          break
        if elem_as_array:
          array_data_chunks+=self.pointer_data_to_chunks(value_idx,value_idx_name,path_idx,deref_depth,**kwargs)
        else:
          array_data_chunks+=self.value_to_chunks_1(value_idx,value_idx_name,path_idx,deref_depth,**kwargs)
        if delimiter and i!=n22-1:
          array_data_chunks.append(delimiter)
      array_data_chunks.append({'str':'\n'})
      chunks1.append({'chunks':array_data_chunks,'type_code':'TYPE_CODE_ARRAY'})
      chunks.append({
        'str':'[\n',
        'onclick_data':self.base_onclick_data('collapse_variable',funcname=funcname,path=path)
      })
      chunks.append ({
        'chunks'  : chunks1,
        'name'    : 'parenthesis',
      })
      chunks.append({
        'str':'\n]\n',
        'onclick_data':self.base_onclick_data('collapse_variable',funcname=funcname,path=path)
      })
    else:
      chunks.append({'str':'[CantAccsMem]'})
    return chunks

  def base_onclick_data(self,cmdname,**kwargs):
    onclick_data = {
      'click_cmd':cmdname,
    }
    onclick_data.update(kwargs)
    return onclick_data

  def collapsed_struct_to_chunks(self,path, **kwargs):
    return self.collapsed_item_to_chunks(path,'{<Expand>}', **kwargs)

  def collapsed_array_to_chunks(self,path, **kwargs):
    return self.collapsed_item_to_chunks(path,'[<Expand>]', **kwargs)


  def collapsed_item_to_chunks(self,path,collapsed_str,**kwargs):
    return [{
        'str':collapsed_str,
        'onclick_data':self.base_onclick_data('expand_variable',path=path,funcname=kwargs.get('funcname')),
      }]


  def pointer_data_to_chunks (self,value,name,path,deref_depth, **kwargs):
    str_type = str(value.type.strip_typedefs())
    assert not re.match('.*void \*$',str_type)
    assert not is_incomplete_type_ptr(value)
    if  kwargs.get('disable_dereference') :
      return []
    if value.is_optimized_out:
      return self.name_to_chunks(name)+[{'str':'<OptimizedOut>'}]
    funcname=kwargs.get('funcname')
    chunks=[]
    if funcname and self.user_slice.get((funcname,path)):
      n1,n2 = self.user_slice.get((funcname,path))
    else:
      deref_type_code = value.dereference().type.strip_typedefs().code
      if deref_type_code in (gdb.TYPE_CODE_STRUCT,gdb.TYPE_CODE_UNION,gdb.TYPE_CODE_FUNC):
        n1,n2=(0,None)
      else:
        n1,n2=(0,2)
    chunks+=self.array_to_chunks(value,name,n1,n2,path,deref_depth+1, **kwargs)
    return chunks


  def pointer_to_chunks (self, value, name, path, deref_depth, **kwargs):
    chunks=[]
    if name:
      chunks+=self.value_type_to_chunks(value,**kwargs)
      chunks.append({'str':' '})
      chunks+=self.name_to_chunks(name)
    chunks += self.changable_value_to_chunks(value,path,**kwargs)
    return chunks

  def name_to_chunks(self,name,**kwargs):
    with_equal=kwargs.get('with_equal',True)
    chunks=[]
    if name!=None:
      if type(name) is str:
        chunks+=[{'str':name, 'name':'varname'},]
      else:
        chunks+=name
      if with_equal:
        chunks+=[{'str':' = '}]
    return chunks

  def changable_value_to_chunks(self,value,path,**kwargs):
    valuestr  = stringify_value_safe(value,**kwargs)
    if 'proposed_text' not in kwargs:
      kwargs['enable_additional_text']=False
      strvalue_pure=stringify_value_safe(value,**kwargs)
      kwargs['proposed_text'] = strvalue_pure
    valuetype1 = str(value.type)
    valuetype2 = str(value.type.strip_typedefs())
    if valuetype1==valuetype2:
      valuetype=valuetype1
    else:
      valuetype='{} aka {}'.format(valuetype1,valuetype2)
    return self.changable_strvalue_to_chunks(valuestr,path,valuetype,**kwargs)

  def changable_strvalue_to_chunks(self,valuestr,path,valuetype,**kwargs):
    onclick_data={
      'click_cmd':'change_variable',
      'path':path,
      'input_text': '{type} {path}'.format(path=path,type=valuetype),
    }
    res={'str':valuestr,'name':'varvalue', 'onclick_data':onclick_data, 'onclick_user_input':True}
    if 'proposed_text' in kwargs:
      res['proposed_text']=kwargs['proposed_text']
    return [res]



  def struct_to_chunks(self,value,name,path,deref_depth, **kwargs):
    already_deref = kwargs['already_deref']
    type_code = value.type.strip_typedefs().code
    chunks=[]
    if name:
      chunks+=self.value_type_to_chunks(value,**kwargs)
      chunks.append({'str':' '})
      chunks+=self.name_to_chunks(name)
    funcname=kwargs.get('funcname')
    valueloc=(funcname,path)
    try:
      value_addr = value.address
    except gdb.MemoryError:
      value_addr=None
    is_already_deref = value_addr!=None and value_addr in already_deref
    if ((deref_depth>=kwargs.get('max_deref_depth',3) or is_already_deref) and not self.expand_variable.get((funcname,path))) or \
        (valueloc in self.expand_variable and not self.expand_variable[(funcname,path)] ):
      chunks += self.collapsed_struct_to_chunks(path, **kwargs)
      return chunks

    if value_addr!=None:
      already_deref.add(value_addr)

    chunks1=[]
    data_chunks=[]
    for field in value.type.fields():
      field_name = field.name
      field_value = value[field_name]
      value_path='{path}.{field_name}'.format(path=path,field_name=field_name)
      data_chunks+=self.value_to_chunks_1(field_value,field_name,value_path,deref_depth,**kwargs)
      data_chunks.append({'str':'\n'})
    if type_code==gdb.TYPE_CODE_STRUCT:
      chunks1.append({'chunks':data_chunks,'type_code':'TYPE_CODE_STRUCT'})
    elif type_code==gdb.TYPE_CODE_UNION:
      chunks1.append({'chunks':data_chunks,'type_code':'TYPE_CODE_UNION'})
    chunks.append({
      'str':'{\n',
      'onclick_data':self.base_onclick_data('collapse_variable',funcname=funcname,path=path),
    })
    chunks.append ({
      'chunks'  : chunks1,
    })
    chunks.append({
      'str':'\n}\n',
      'onclick_data':self.base_onclick_data('collapse_variable',funcname=funcname,path=path),
    })
    return chunks



  def value_to_chunks(self,value,name=None,**kwargs):
    ''' Конвертирование gdb.Value в json-дерево.

        Args:
            value (gdb.Value): значение, которое нужно сконвертировать в json
            name (str): Имя, которое используется для печати NAME = VALUE. Если не задано,
                то напечатается просто VALUE.
            **funcname (str): имя функции, в контексте которой value конвертируется в json.
            **max_deref_depth (int, default=3): Данный параметр используется для ограничения dereference указателей.
                В рамках преобразования, которое делает данная функция для каждого указателя будет напечатан не только
                адрес, но и значение памяти. Если представить список из миллиона элементов, то, очевидно, что весь
                список печатать не надо.
            **already_deref (set): множество, состоящее из целых чисел. Кадое число трактуется, как адрес.
                Для каждого адреса из данного множества разыменование производиться не будет.
    '''
    path=name
    deref_depth=0
    already_deref = set()
    if 'funcname' not in kwargs:
      kwargs['funcname'] = self._get_frame_funcname(gdb.selected_frame())
    if 'already_deref' not in kwargs:
      kwargs['already_deref'] = set()
    return self.value_to_chunks_1(value,name,path,deref_depth,**kwargs)

  def value_withstr_to_chunks(self,value,name,path,deref_depth,**kwargs):
    chunks=[]
    chunks+=self.name_to_chunks(name)
    chunks.append({'str':stringify_value_safe(value,enable_additional_text=True), 'name':'varvalue'})
    #chunks+=self.value_to_str_chunks(value,path,enable_additional_text=True,**kwargs)
    return chunks

  def possible_read_memory_ptr(self,value,**kwargs):
    assert value.type.strip_typedefs().code==gdb.TYPE_CODE_PTR
    n1=kwargs.get('n1',0)
    addr=ctypes.c_ulong(long(value)).value
    size=value.dereference().type.sizeof
    return self.possible_read_memory(addr+n1*size,size)

  def possible_read_memory(self,addr,size):
    if addr<0:
      return False
    infer = gdb.selected_inferior ()
    if infer==None:
      return False
    try:
      infer.read_memory (addr,size)
      return True
    except gdb.MemoryError:
      return False

  def ptrval_to_ulong(self,value):
    return ctypes.c_ulong(long(value)).value

  def functionptr_to_chunks(self,value, name, path, deref_depth, **kwargs):
    chunks=[]
    func_addr = self.ptrval_to_ulong(value)
    function=None
    try:
      block=gdb.block_for_pc (func_addr)
    except RuntimeError:
      block=None
    while block:
      if block.function:
        function = block.function
        break
      block=block.superblock
    if function:
      func_name=function.name
    else:
      func_name='unknown'
    if name:
      chunks+=self.value_type_to_chunks(value,**kwargs)
      chunks.append({'str':' '})
      chunks+=self.name_to_chunks(name)
    #chunks.append({'str':hex(func_addr)[:-1]})
    chunks+=self.changable_value_to_chunks(value,path,**kwargs)
    chunks.append({'str':' '})
    chunks.append({'str':'<{}>'.format(func_name)})
    return chunks



  def functionptr_to_chunks_argtypes(self,value, name, path, deref_depth, **kwargs):
    arg_types = [field.type for field in value.dereference().type.fields()]
    return_type = value.dereference().type.strip_typedefs().target()
    func_addr = self.ptrval_to_ulong(value)
    func_name='unknown'
    try:
      block=gdb.block_for_pc (func_addr)
    except RuntimeError:
      block=None
    while block:
      if block.function:
        func_name = block.function.name
        break
      block=block.superblock
    chunks=[]
    chunks.append({'str':'{'})
    chunks.append({'str':str(return_type),'name':'datatype'})
    chunks.append({'str':' '})
    chunks.append({'str':'('})
    arg_chunks=[{'str':str(arg_type),'name':'datatype'} for arg_type in arg_types]
    if len(arg_chunks)>0:
      arg_chunks_commas=[]
      arg_chunks_commas.append(arg_chunks[0])
      for arg_chunk in arg_chunks[1:]:
        arg_chunks_commas.append({'str':','})
        arg_chunks_commas.append(arg_chunk)
      chunks+=arg_chunks_commas
    chunks.append({'str':')'})
    chunks.append({'str':'}'})
    chunks.append({'str':' '})
    chunks.append({'str':hex(func_addr)[:-1]})
    chunks.append({'str':' '})
    chunks.append({'str':'<{}>'.format(func_name)})
    return chunks

  def value_type_to_chunks(self,value,**kwargs):
    type_code=value.type.strip_typedefs().code
    if type_code==gdb.TYPE_CODE_STRUCT:
      return [{'str':'struct','name':'datatype'}]
    elif type_code==gdb.TYPE_CODE_UNION:
      return [{'str':'union','name':'datatype'}]
    else:
      return [{'str':str(value.type),'name':'datatype'}]

  def value_to_chunks_1(self,value,name,path,deref_depth,**kwargs):
    ''' Конвертирование gdb.Value в json-дерево. Рекурсия.
        Дополнительное описание см. в функции `value_to_chunks`

        Args:
            path_parent (str): Используется для определения местонахождения переменной.
                Напр., рассмотр. структуру s, которая сод. структуру y. s={x:1,y:{a:5,b:2}, arr[2] = {A0,A1} }
                При печати структуры y ей будет передан path_parent='s'. На основе
                path_parent будет сформирован path у дочерних полей. Напри., s.y.a будет иметь path
                "s.y.a", для элемента массива A1 path = "s.arr[1]"
            path_name (str): Применяется для формирования path. Совпадает с именем переменной, за исключением
                элементов массивов. Для A0 path_name будет arr[0]. Для массива arr path_name="arr".
            deref_depth (int): текущая глубина разыменования. Если deref_depth==max_deref_depth, то указатель
                будет напечатан без разыменования.
            **deref_depth_max (int): см. deref_depth
            **already_deref (set): мн-во указателей, которые уже были разменованы. Если была напечатана структура или массив,
                которая определена статически, то будет взят адрес данной структуры и помещен в данное множество.
                Рассмотрим двунапр. данное мн-во
                предотвр. ситуацию, когда процесс разыменования дошел до конца списка, а потом начал разыменовывать указатели
                на предыдущие элементы, потом вновь разыменовывать next-элементы....
            **disable_dereference (bool): Если True, то dereference делаться не будет. По умолчанию False.

    '''
    #path = self.append_path(path_parent,path_name)
    chunks=[]
    type_code = value.type.strip_typedefs().code
    type_str = str(value.type.strip_typedefs())
    funcname=kwargs.get('funcname')
    if type_code in (gdb.TYPE_CODE_STRUCT,gdb.TYPE_CODE_UNION):
      chunks+=self.struct_to_chunks(value,name,path,deref_depth,**kwargs)
    elif type_code==gdb.TYPE_CODE_ARRAY:
      array_addr = value.address
      if array_addr!=None:
        pointer_chunks = self.pointer_to_chunks (array_addr, name, path, deref_depth, **kwargs)
        if len(pointer_chunks)!=0:
          chunks+=pointer_chunks
          chunks.append({'str':'\n'})
      if re.match('.*char \[.*\]$',type_str):
        chunks+=self.value_withstr_to_chunks(value,name,path,deref_depth,**kwargs)
      else:
        n1_orig,n2_orig = value.type.range()
        funcname=kwargs['funcname']
        user_slice = self.user_slice.get((funcname,path))
        if user_slice:
          n1,n2 = user_slice
          n1 = max(n1,n1_orig)
          if n2!=None:
            n2 = min(n2,n2_orig)
        else:
          n1,n2 = n1_orig,n2_orig
        chunks += self.array_to_chunks (value, name, n1, n2, path, deref_depth, **kwargs)
    elif type_code==gdb.TYPE_CODE_PTR:
      if re.match('.*char \*$',type_str):
        #строку печатаем по-другому в сравнении с обычным pointer
        if name:
          chunks+=self.value_type_to_chunks(value,**kwargs)
          chunks.append({'str':' '})
          chunks+=self.name_to_chunks(name)
        chunks+=self.changable_value_to_chunks(value,path,enable_additional_text=True,**kwargs)
      else:
        is_funct_ptr=False
        pointer_data_chunks = []
        if not value.is_optimized_out and not re.match('.*void \*$',type_str) and not is_incomplete_type_ptr(value):
          #все OK
          if value.dereference().type.strip_typedefs().code==gdb.TYPE_CODE_FUNC:
            is_funct_ptr=True
          else:
            pointer_data_chunks = self.pointer_data_to_chunks (value, name, path, deref_depth, **kwargs)
        if is_funct_ptr:
          pointer_chunks = self.functionptr_to_chunks(value, name, path, deref_depth, **kwargs)
        else:
          pointer_chunks = self.pointer_to_chunks (value, name, path, deref_depth, **kwargs)
        chunks+=pointer_chunks
        if len(pointer_data_chunks) > 0:
          chunks+=[{'str':'\n'}]
          chunks+=pointer_data_chunks


    else:
      if  name!=None:
        chunks+=self.value_type_to_chunks(value,**kwargs)
        chunks.append({'str':' '})
        chunks+=self.name_to_chunks(name)
      chunks+=self.changable_value_to_chunks(value,path,**kwargs)
    return chunks

  def make_slice_chunk_auto(self,path,funcname):
    n1,n2 = self.user_slice.get((funcname,path),(0,None))
    return self.make_slice_chunk(n1,n2,path,funcname)

  def make_slice_chunk(self,n1,n2,path,funcname):
    chunks=[]
    chunks.append({'str':'[','name':'slice'})
    if n2==None:
      chunks.append({'str':str(n1),'name':'slice'})
    else:
      chunks.append({'str':str(n1),   'name':'slice'})
      chunks.append({'str':':',                  'name':'slice'})
      chunks.append({'str':str(n2),  'name':'slice'})
    chunks.append({'str':']','name':'slice'})
    onclick_data={
      'click_cmd':'change_slice',
      'path':path,
      'funcname':funcname,
      'input_text':'enter new slice N or N:M',
    }
    slice_chunk={
      'chunks':chunks,
      'onclick_data':onclick_data,
      'onclick_user_input':True,
    }
    return slice_chunk

  def _get_local_vars_chunks(self):
    variables = self._get_local_vars_1 ()
    if len(variables)==0:
      return []
    lvars=[]
    funcname=self._get_frame_funcname(gdb.selected_frame())
    for name,value in variables.iteritems():
      #kwargs={}
      chunks = self.value_to_chunks(value,name,funcname=funcname)
      check_chunks(chunks)
      col = {'chunks':chunks}
      row = {'columns':[col]}
      lvars.append(row)
    #lvars.sort( cmp = lambda x,y: 1 if x[''][0][0]['str']>y[0][0]['str'] else -1 )
    return {'rows':lvars}

  def _get_local_vars_1(self):
    try:
      frame = gdb.selected_frame()
    except gdb.error:
      return []
    if not frame:
      return []
    try:
      block = frame.block()
    except RuntimeError:
      return []
    variables = {}
    while block:
      for symbol in block:
        if (symbol.is_argument or symbol.is_variable):
            name = symbol.name
            if name not in variables:
              variables[name] = symbol.value(frame)
      if block.function:
        break
      block = block.superblock
    return variables


  def _get_frame_func_args(self,frame):
      args=[]
      try:
        block=frame.block()
      except RuntimeError:
        return []
      while block:
        for sym in block:
          if sym.is_argument:
            value = sym.value(frame)
            args.append(
              (sym.name,stringify_value_safe(value))
            )
        if block.function:
          break
        block=block.superblock
        if (not block):
          break
      return args

  def _get_frame_funcname(self,frame):
    frame_func_name = frame.name()
    return frame_func_name

  def _get_frame_funcname_with_args(self,frame):
    frame_func_name = {'str':self._get_frame_funcname(frame),'name':'frame_func_name'}
    frame_func_args = []
    func_args = self._get_frame_func_args(frame)
    for argname,argval in func_args:
      frame_func_args.append({'str':'\n  '})
      frame_func_args.append({'str':argname,'name':'varname'})
      frame_func_args.append({'str':'='})
      frame_func_args.append({'str':argval, 'name':'varvalue'})
    res = [frame_func_name, {'str':'('}] + frame_func_args
    if len(func_args) > 0:
      res.append ({'str':'\n)'})
    else :
      res.append ({'str':')'})
    return res


  def _get_frame_fileline(self,frame):
    frame_line      = frame.find_sal().line
    symtab = frame.find_sal().symtab
    frame_filename  = symtab.filename if symtab else 'unknown'
    return [
      {'str':frame_filename,'name':'frame_filename'},
      {'str':':', 'name':'frame_fileline_delimiter'},
      {'str':str(frame_line),'name':'frame_line'},
    ]

  def _get_stack_1(self):
    frame = gdb.newest_frame ()
    nframe=0
    frames=[]
    selected_row=None
    while frame:
      col={}
      framenumber = {'str':'#{}'.format(str(nframe)),'name':'frame_num'}
      if frame == gdb.selected_frame ():
        framenumber['selected']=True
        selected_row=nframe
      col['onclick_data']={
          'click_cmd':'select_frame',
          'nframe' : nframe,
        }
      chunks = [
        framenumber,
        {'str':'  '},
      ] + self._get_frame_fileline(frame) + \
      [
        {'str':'\n'},
      ] + self._get_frame_funcname_with_args(frame)
      col['chunks']=chunks
      row = {'columns' : [col], 'nframe':nframe}
      frames.append(row)
      nframe+=1
      frame = frame.older()
    table={
      'rows':frames,
    }
    if selected_row!=None:
      table['selected_row'] = selected_row
    return table

  def get_stack(self):
    return exec_in_main_pythread (self._get_stack_1,())

  def _get_regs_1(self):
    rows_regs=[]
    for regname in self.regnames:
      regvalue = gdb.parse_and_eval(regname)
      chunks = self.value_to_chunks(regvalue,regname, integer_as_hex=True, disable_dereference=True)
      col  = {'chunks' : chunks}
      row  = {'columns' : [col]}
      rows_regs.append(row)
    return {'rows' : rows_regs}

  def get_registers(self):
    if not gdb_stopped() or not inferior_alive ():
      return
    return exec_in_main_pythread (self._get_regs_1,())

  def _get_threads_1(self):
    selected_thread = gdb.selected_thread()
    throws=[]
    threads=gdb.selected_inferior().threads()
    nrow=0
    selected_row=None
    for thread in threads:
      column={}
      thread.switch()
      frame = gdb.selected_frame()
      global_num    =   str(thread.global_num)
      tid           =   str(thread.ptid[1])
      threadname    =   str(thread.name) if thread.name else ''
      funcname      =   self._get_frame_funcname_with_args(frame)
      fileline      =   self._get_frame_fileline(frame)
      global_num_chunk = {'str':global_num, 'name':'th_global_num'}
      if thread==selected_thread:
        global_num_chunk['selected']=True
        selected_row=nrow
      column['onclick_data'] = {
          'click_cmd':'select_thread',
          'nthread' : nrow,
        }
      chunks = [ global_num_chunk,
          {'str':'  '},
          {'str':tid,        'name':'th_tid'},
          {'str':'  '},
          {'str':'"'},
          {'str':threadname,     'name':'th_threadname'},
          {'str':'"\n'},
        ] +  \
        fileline + \
        [{'str':'\n'}] + \
        self._get_frame_funcname_with_args(frame)
      column['chunks'] = chunks
      row={'columns' : [column]}
      throws.append(row)
      nrow+=1
    if selected_thread!=None:
      selected_thread.switch()
    table = {
      'rows':throws,
    }
    if selected_row!=None:
      table['selected_row'] = selected_row
    return table

  def get_threads(self):
    return exec_in_main_pythread (self._get_threads_1,())

  def update_all(self):
    self.update_localvars()
    self.update_backtrace()
    self.update_registers()
    self.update_threads()

  def process_gdbevt(self,name,evt):
    if name=='cont':
      pass
    elif name=='exited':
      self.update_all()
    elif name=='stop':
      self.update_all()
    elif name=='new_objfile':
      self.update_all()
    elif name=='clear_objfiles':
      self.update_all()
    elif name=='inferior_call_pre':
      pass
    elif name=='inferior_call_post':
      pass
    elif name=='memory_changed':
      self.update_localvars()
      self.update_registers()
    elif name=='register_changed':
      pass
    elif name=='breakpoint_created':
      pass
    elif name=='breakpoint_modified':
      pass
    elif name=='breakpoint_deleted':
      pass

  def process_shellcmd(self,cmdname):
    if cmdname=='quit':
      pass
    elif cmdname=='bp_disable':
      pass
    elif cmdname=='bp_enable':
      pass
    elif cmdname=='frame_up':
      self.update_all()
    elif cmdname=='frame_down':
      self.update_all()
    elif cmdname=='frame':
      self.update_all()
    elif cmdname=='thread':
      self.update_all()




class MainWindow(BaseWindow):

  type='main_window'
  startcmd='mcgdb open main'


  def __init__(self, **kwargs):
    super(MainWindow,self).__init__(**kwargs)
    self.window_event_handlers.update({
      'editor_breakpoint'       :  self.__editor_breakpoint,
      'editor_breakpoint_de'    :  self.__editor_breakpoint_de,
    })
    self.exec_filename=None #текущему фрейму соответствует это имя файла с исходным кодом
    self.exec_line=None     #номер строки текущей позиции исполнения программы
    self.edit_filename=None #Файл, который открыт в редакторе. Отличие от self.exec_filename в
                            #том, что если исходник открыть нельзя, то открывается файл-заглушка.

  def process_connection(self):
    rc=super(MainWindow,self).process_connection()
    if rc:
      self.update_current_frame()
      self.update_breakpoints()
    return rc


  def process_gdbevt(self,name,evt):
    if name=='cont':
      pass
    elif name=='exited':
      self.update_current_frame()
    elif name=='stop':
      self.update_current_frame()
      self.update_breakpoints()
    elif name=='new_objfile':
      self.update_current_frame()
    elif name=='clear_objfiles':
      self.update_current_frame()
    elif name=='inferior_call_pre':
      pass
    elif name=='inferior_call_post':
      pass
    elif name=='memory_changed':
      pass
    elif name=='register_changed':
      pass
    elif name=='breakpoint_created':
      self.update_breakpoints()
    elif name=='breakpoint_modified':
      self.update_breakpoints()
    elif name=='breakpoint_deleted':
      self.update_breakpoints()

  def process_shellcmd(self,cmdname):
    if cmdname=='quit':
      pass
    elif cmdname=='bp_disable':
      pass
    elif cmdname=='bp_enable':
      pass
    elif cmdname=='frame_up':
      self.update_current_frame()
    elif cmdname=='frame_down':
      self.update_current_frame()
    elif cmdname=='frame':
      self.update_current_frame()


  def update_current_frame(self):
    '''Данная функция извлекает из gdb текущий файл
        и номер строки исполнения. После чего, если необходимо, открывает
        файл с исходником в редакторе и перемещает экран к линии исполнения.
    '''
    filename,line = self.get_current_position()
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
        dname=os.path.dirname(TMP_FILE_NAME)
        if not os.path.exists(dname):
          os.makedirs(dname)
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
    assert self.edit_filename!=None
    self.exec_filename=filename
    self.exec_line=line


  def update_breakpoints(self):
    normal=breakpoint_queue.get_bps_locs_normal(self.edit_filename)
    disabled=breakpoint_queue.get_bps_locs_disabled(self.edit_filename)
    wait_remove=breakpoint_queue.get_bps_locs_wait_remove(self.edit_filename)
    wait_insert=breakpoint_queue.get_bps_locs_wait_insert(self.edit_filename)
    pkg={
      'cmd':'breakpoints',
      'normal'          :   normal,
      'wait_insert'     :   wait_insert,
      'wait_remove'     :   wait_remove,
      'disabled'        :   disabled,
      'remove'          :   [],
      'clear':True,
    }
    self.send(pkg)

  #commands from editor
  def __editor_breakpoint(self,pkg):
    line=pkg['line']
    if self.edit_filename==TMP_FILE_NAME:
      #в редакторе открыт файл-заглушка.
      #молча игнорируем попытки манипуляцией брейкпоинтами
      return
    breakpoint_queue.insert_or_delete(self.edit_filename,line)
    breakpoint_queue.process()
    return [{'cmd':'check_breakpoint'}]
  def __editor_breakpoint_de(self,pkg):
    ''' Disable/enable breakpoint'''
    raise NotImplementedError
    breakpoint_queue.process()

  def set_color(self,pkg):
    self.send(pkg)





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
    type=pkg['type']
    manually=pkg.get('manually',False)
    cls={
      'main'        :   MainWindow,
      'localvars'   :   LocalVarsWindow,
    }
    WinClsConstr=cls.get(type)
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
      try:
        os.remove(TMP_FILE_NAME)
      except:
        pass
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



class McgdbMain(object):
  def __init__(self):
    if not self.__is_gdb_version_correct():
      return
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

    self.open_window('main')
    self.open_window('localvars')

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


def init():
  global mcgdb_main
  mcgdb_main = McgdbMain()

def module_initialized():
  return not mcgdb_main==None


init()

######################## GDB commands ############################


def start_with(arr,word):
  return [s for s in arr if s[:len(word)]==word]


class McgdbCompleter (gdb.Command):
  def __init__ (self):
    super (McgdbCompleter, self).__init__ ("mcgdb", gdb.COMMAND_USER, gdb.COMPLETE_COMMAND, True)
McgdbCompleter()

class CmdOpenWindow (gdb.Command):
  """ Open mcgdb main window with current source file and current execute line

      Options:
      --manually if specified, then gdb will not start window, instead
          gdb only print shell command. User must manually copypaste given
          command into another terminal.
  """

  def __init__ (self):
    super (CmdOpenWindow, self).__init__ ("mcgdb open", gdb.COMMAND_USER)
    self.permissible_options=['--manually']
    self.types=['main', 'localvars']

  def invoke (self, arg, from_tty):
    self.dont_repeat()
    if not module_initialized():
      init()
    args=arg.split()
    if len(args)==0:
      print 'number of args must be >0'
      return
    type=args[0]
    options=args[1:]
    unknown_options=[opt for opt in options if opt not in self.permissible_options]
    if len(unknown_options) > 0:
      print 'unknown options: {}'.format(unknown_options)
    manually=('--manually' in options)
    if type not in self.types:
      print '`type` should be in {}'.format(self.types)
      return
    mcgdb_main.open_window(type,manually=manually)

  def complete(self,text,word):
    complete_part = text[:len(text)-len(word)]
    narg=len(complete_part.split())
    if narg==0:
      return start_with(self.types,word)
    if narg >= 1:
      return gdb.COMPLETE_NONE


CmdOpenWindow()


class CmdColor (gdb.Command):
  '''Change color in editor.
USAGE: mcgdb color type text_color background_color [attribs]

type={curline, bp_normal, bp_disabled, bp_wait_remove, bp_wait_insert}
COLOR={black, white, blue, yellow, red, ...}
attrib={bold, italic, underline, reverse, blink}
text_color: see COLOR set
background_color: see COLOR set
attribs: attrib1+...+attrinb
'''

  def __init__ (self):
    super (CmdColor, self).__init__ ('mcgdb color', gdb.COMMAND_USER)
    self.cbs={
      'curline'        : mcgdb_main.set_color_curline,
      'bp_normal'      : mcgdb_main.set_color_bp_normal,
      'bp_disabled'    : mcgdb_main.set_color_bp_disabled,
      'bp_wait_remove' : mcgdb_main.set_color_bp_wait_remove,
      'bp_wait_insert' : mcgdb_main.set_color_bp_wait_insert,
    }
    self.colors=[
      'black', 'gray', 'red', 'brightred', 'green', 'brightgreen',
      'brown', 'yellow', 'blue', 'brightblue', 'magenta', 'brightmagenta',
      'cyan', 'brightcyan', 'lightgray', 'white',
    ]
    self.attribs= [
      'bold', 'italic', 'underline', 'reverse', 'blink',
    ]
    self.types=self.cbs.keys()

  def invoke (self, arg, from_tty):
    args=arg.split()
    if len(args)!=3 and len(args)!=4:
      print 'number of args must be 3 or 4'
      return
    if len(args)==3:
      type,text_color,background_color = tuple(args)
      attribs=None
    else:
      type,text_color,background_color,attribs = tuple(args)
    if type not in self.types:
      print '`type` should be in {}'.format(self.types)
      return
    if text_color not in self.colors:
      print '`text_color` should be in {}'.format(self.colors)
      return
    if background_color not in self.colors:
      print '`background_color` should be in {}'.format(self.colors)
      return
    if attribs:
      attribs_arr=attribs.split('+')
      for attrib in attribs_arr:
        if attrib not in self.attribs:
          print '`attrib` should be in {}'.format(self.attribs)
          return
    self.cbs[type](text_color,background_color,attribs)

  def complete(self,text,word):
    complete_part = text[:len(text)-len(word)]
    narg=len(complete_part.split())
    #gdb.write( 'nargs={narg} word=`{word}`'.format( word=word,narg=narg ) )
    if narg==0:
      return start_with(self.types,word)
    if narg==1 or narg==2:
      return start_with(self.colors,word)
    if narg==3:
      return start_with(self.attribs,word)
    if narg >= 4:
      return gdb.COMPLETE_NONE


CmdColor()









