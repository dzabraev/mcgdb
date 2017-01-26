#coding=utf8
import gdb
import threading
import socket
import select
import os,stat
import sys
import re
import errno

class window_type:
  MCGDB_MAIN_WINDOW         = "mcgdb_main_window"
  MCGDB_SOURCE_WINDOW       = "mcgdb_source_window"
  MCGDB_BACKTRACE_WINDOW    = "mcgdb_backtrace_window"


gdb_listen_port=None
stop_event_loop_flag=False
local_w_fd=None #В этот дескриптор можно писать команды из gdb
event_thread=None #данный поток обрабатывает команды из окон с mcedit и из gdb
PATH_TO_MC="/home/dza/bin/mcedit"
PATH_TO_DEFINES_MCGDB="~/bin/defines-mcgdb.gdb"
window_queue=[]
__mcgdb_initialized=False
TMP_FILE_NAME="/tmp/mcgdb-tmp-file-{pid}.txt".format(pid=os.getpid())

#need_processing_bp=[]
#need_processing_bp_mutex=threading.Lock()

class DebugPrint(object):
  called=1
  new_worker=2
  mcgdb_communicate_protocol=3
  events=4

verbose=[
  #DebugPrint.events,
  #DebugPrint.mcgdb_communicate_protocol,
] # Данный массив используется для регулирования
#отладочного вывода. Данный массив должен заполняться
# свойствами класса DebugPrint
#example: verbose=[DebugPrint.called,DebugPrint.new_worker]

breakpoint_queue=[] #Если inferior не приостановлен и пользователь
#кликает по столбцам с номерами строк, то для добавления и удаления
#точки останова необходимо дождаться остановки inferior. Пока inferior
#запущен будем запоминать точки останова, которые необходимо поставить.

class _FP(object):
  fnew=None
  fold=None
  lnew=None
  lold=None


FP=_FP()

class CommandReadFailure(Exception): pass
class StopEventThread(Exception): pass

def gdb_print(msg,**kwargs):
  #thread safe
  disable_mcgdb_prefix=kwargs.get('disable_mcgdb_prefix',False)
  mcgdb_prefix='' if disable_mcgdb_prefix else '\nmcgdb: '
  msg='{mcgdb_prefix}{origmsg}{prompt}'.format(
    origmsg=msg,
    prompt=gdb.parameter("prompt"),
    mcgdb_prefix=mcgdb_prefix,
  )
  gdb.post_event(lambda : gdb.write(msg))


def recv_cmd(fd):
  data=''
  while True:
    try:
      b=os.read(fd,1)
    except IOError as e:
      if e.errno == errno.EINTR:
        continue
      else:
        raise CommandReadFailure
    except OSError:
      raise CommandReadFailure
    if len(b)==0:
      raise CommandReadFailure
    if b==';':
      break
    data+=b
  sp=data.split(':')
  cmd=sp[0]
  args=sp[1].split(',')
  if DebugPrint.mcgdb_communicate_protocol in verbose:
    gdb_print('recv_cmd({fd}): {data}\n'.format(fd=fd,data=data))
  return (cmd,args)

def send_cmd(fd,cmd):
  if DebugPrint.mcgdb_communicate_protocol in verbose:
    gdb_print('send_cmd({fd}): {data}\n'.format(fd=fd,data=cmd))
  os.write(fd,cmd)

def is_function(loc):
  return gdb.block_for_pc(loc.pc).function!=None

def first_executable_linenum(loc):
  block=gdb.block_for_pc(loc.pc)
  pc_start = block.start  #address of first instruction in function
  pc_stop  = block.end    #address of last instr in func
  first_exec_line=None
  #find first line, whose addr > pc_start and whose
  #correspond to function
  for le in loc.symtab.linetable():
    if le.pc > pc_stop:
      break
    if le.pc > pc_start:
      first_exec_line=le.line
      break
  if first_exec_line==None:
    first_exec_line=loc.line
  return first_exec_line

def get_bp_location(bp,**kwargs):
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



def get_bp(gdb_bps,filename,line):
  for bp in gdb_bps:
    if bp.type!=gdb.BP_BREAKPOINT:
      continue
    try:
      locations=get_bp_location(bp)
    except Exception:
      continue
    for lf,ll in locations:
      #gdb_print('{} {} {} {}\n'.format(ll,line,lf,filename))
      if lf==filename and ll==line:
        return bp
  return None


def bp_check_delete(bp):
  if gdb.selected_thread().is_stopped():
    bp.delete()
    return True
  else:
    return False

def bp_check_insert(filename,line):
  if gdb.selected_thread().is_stopped():
    try:
      exec_in_main_pythread( gdb.Breakpoint, ('{}:{}'.format(filename,line),) )
    except gdb.error:
      pass
    return True
  else:
    return False


def process_breakpoint_queue():
  global breakpoint_queue
  for idx in range(len(breakpoint_queue)):
    bp_request = breakpoint_queue[idx]
    request_type=bp_request[0]
    request_arg =bp_request[1]
    assert request_type in ('delete','insert')
    if request_type=='delete':
      bp=request_arg[0]
      res=exec_in_main_pythread(bp_check_delete , (bp,))
    elif request_type=='insert':
      filename,line=request_arg
      res=exec_in_main_pythread(bp_check_insert , (filename, line))
    if not res:
      #inferior running; can't process breakpoint
      breakpoint_queue = breakpoint_queue[idx:]
      return
  breakpoint_queue=[]

def bp_delete(bp):
  #bp if gdb.Breakpoint object
  global breakpoint_queue
  if DebugPrint.called in verbose: gdb_print('called `bp_delete`\n')
  locations=get_bp_location(bp)
  breakpoint_queue.append ( ('delete',(bp,locations)) )
  process_breakpoint_queue ()

def bp_insert(filename,line):
  global breakpoint_queue
  if DebugPrint.called in verbose: gdb_print('called `bp_insert`\n')
  breakpoint_queue.append ( ('insert',(filename,line)) )
  process_breakpoint_queue ()


def bp_queue_get_request_idx(filename,line):
  for idx in range(len(breakpoint_queue)):
    bp_request=breakpoint_queue[idx]
    request_type=bp_request[0]
    request_arg =bp_request[1]
    assert request_type in ('delete','insert')
    if request_type=='delete':
      bp,locations=request_arg
      if (filename,line) in locations:
        return idx
    elif request_type=='insert':
      request_filename,request_line=request_arg
      if request_filename==filename and request_line==line:
        return idx
  return None


def bp_exists_in_queue(filename,line):
  return bp_queue_get_request_idx(filename,line)!=None

def bp_in_queue(bp):
  for bp_request in breakpoint_queue:
    request_type=bp_request[0]
    if request_type=='delete':
      request_arg=bp_request[1]
      bp_object=request_arg[0]
      if bp_object==bp:
        return True
  return False

def is_current_thread_stopped():
  return exec_in_main_pythread( lambda : gdb.selected_thread().is_stopped(), () )


def insert_or_delete_breakpoint(entities,fd,filename,line):
  if not filename:
    return
  try:
    #check whether line belongs to file
    exec_in_main_pythread( gdb.decode_line, ('{}:{}'.format(filename,line),))
  except:
    #not belonging
    return
  idx=bp_queue_get_request_idx(filename,line)
  if idx!=None:
    #Чётный клик по кнопке. Удаляем request
    global breakpoint_queue
    breakpoint_queue.pop(idx)
    cmd_update_breakpoints(entities,fd,[])
    return
  gdb_bps=exec_in_main_pythread( gdb.breakpoints, ())
  if gdb_bps!=None:
    try:
      bp=get_bp(gdb_bps,filename,line)
    except gdb.error:
      return
  else:
    bp=None
  if bp!=None:
    #exists bp at (filename,line)
    bp_delete(bp)
  else:
    #create breakpoint
    bp_insert(filename,line)
    if is_current_thread_stopped():
      gdb_print('',disable_mcgdb_prefix=True)
  cmd_update_breakpoints(entities,fd,[])


def cmd_insert_or_delete_breakpoint(entities,fd,args):
  filename=entities[fd]['filename_in_editor']
  if not filename:
    return
  line = int(args[0])
  insert_or_delete_breakpoint(entities,fd,filename,line)


def cmd_mouse_click(entities,fd,args):
  filename=args[0] #in this file user produce click
  col  = int(args[1])
  line = int(args[2])
  click_types = args[3].split('|')
  if DebugPrint.events in verbose:
    gdb_print('fname={} col={} line={} click_types={}'.format(
    filename,col,line,click_types))
  #gdb_print("mouse click in mc col={} line={} types={}\n".format(col,line,click_types))
  if 'MSG_MOUSE_DOWN' in click_types and col<=7:
    #do breakpoint
    insert_or_delete_breakpoint(entities,fd,filename,line)

def cmd_mcgdb_main_window(entities,fd,args):
  return cmd_mcgdb_window(entities,fd,args,window_type.MCGDB_MAIN_WINDOW)

def cmd_mcgdb_backtrace_window(entities,fd,args):
  return cmd_mcgdb_window(entities,fd,args,window_type.MCGDB_BACKTRACE_WINDOW)


def cmd_mcgdb_window(entities,fd,args,wtype):
  if wtype in (
      window_type.MCGDB_MAIN_WINDOW,
      window_type.MCGDB_BACKTRACE_WINDOW):
    for entity_fd in entities:
      entity=entities[entity_fd]
      if entity['type']==wtype:
        gdb_print('{} already exists\n'.format(wtype))
        return
  window_queue.append({'type':wtype})
  if DebugPrint.called in verbose:
    gdb_print("called cmd_mcgdb_window\n")
  os.system('gnome-terminal -e "{path_to_mc} -e --gdb-port={gdb_port}"'.format(
    path_to_mc=PATH_TO_MC,gdb_port=gdb_listen_port))



def cmd_mcgdb_source_window(entities,fd,args):
  window_queue.append({
    'type':window_type.MCGDB_SOURCE_WINDOW,
    'filename':args[0],
    'line':args[1],
  })

def fetch_and_process_command(entities,fd,cmds):
  cmd,args=recv_cmd(fd)
  try:
    callback=cmds[cmd]
  except KeyError:
    gdb_print("bad command received: `{}`\n".format(cmd))
    return
  return callback(entities,fd,args)

__exec_in_main_pythread_result=None

def __exec_in_main_pythread(func,args,evt):
  global __exec_in_main_pythread_result
  try:
    if DebugPrint.called in verbose:
      gdb.write('called __exec_in_main_pythread\n')
    __exec_in_main_pythread_result=('ok',func(*args))
  except Exception:
    t, v, tb = sys.exc_info()
    __exec_in_main_pythread_result=('exception',t, v, tb)
  evt.set()

def is_main_thread():
  return threading.current_thread().ident==main_thread_ident


def exec_in_main_pythread(func,args):
  #Данную функцию нельзя вызывать более чем из одного потока
  global __exec_in_main_pythread_result
  if is_main_thread():
    return func(*args)
  else:
    evt=threading.Event()
    gdb.post_event(
      lambda : __exec_in_main_pythread(func,args,evt)
    )
    evt.wait()
  if __exec_in_main_pythread_result[0]=='ok':
    return __exec_in_main_pythread_result[1]
  else:
    _,t,v,tb=__exec_in_main_pythread_result
    raise t,v,tb


def get_abspath(filename):
  #Данную функцию можно вызывать только из main pythread или
  #через функцию exec_in_main_pythread
  info=gdb.execute('info source {}'.format(filename),False,True)
  inf=str(info)
  ss=inf.split('\n')[2]
  abspath=re.sub(r'.*Located in (.*)',r'\1',ss)
  return abspath


def update_FP():
  #Данную функцию можно вызывать только из main pythread или
  #через функцию exec_in_main_pythread
  global FP
  FP.force_reopen=False
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
  if not filename or not os.path.exists(filename) or not ( os.stat(filename).st_mode & stat.S_IFREG ):
    #текущий файл неизвестен или не существует
    with open(TMP_FILE_NAME,'w') as f:
      if not filename:
        f.write('\nCurrent execution position and source file not known.\n')
      else:
        f.write('\nFilename {} not exists\n'.format(filename))
    filename=TMP_FILE_NAME
    line=1
    FP.force_reopen=True
  FP.fold=FP.fnew
  FP.fnew=filename #currrently debugged file
  FP.lold=FP.lnew  #currrently debugged line
  FP.lnew=line

def cmd_inferior_exited(entities,fd,args):
  #exit_code=args[0]
  cmd_check_frame(entities,fd,[])

def get_cmd_insert_bp_all(fname):
  cmd=''
  try:
    bps=exec_in_main_pythread(gdb.breakpoints, ())
  except gdb.error:
    return cmd
  for bp in bps:
    try:
      locations=get_bp_location(bp)
    except gdb.error:
      continue
    for bpfname,bpline in locations:
      if bpfname==fname:
        cmd+='insert_bp:{};'.format(bpline)
  return cmd

def cmd_check_frame(entities,fd,args):
  # Нужно изменить файл и/или позицию в файле
  # в main mc window. Если существует не main mc window,
  # и в нем открыт файл filename, то нужно подкрасить в нем
  # текущую строчку. При этом если существовало не main mc window,
  # в котором была подкрашена текущая строчка, то покраску с нее
  # необходимо снять.
  cmd_for_main_window=None
  if DebugPrint.called in verbose:
    gdb_print('called `cmd_check_frame`')
  main_mc_window_fd=None
  mc_windows_fds=[]
  for fd in entities:
    entity=entities[fd]
    if entity['type']==window_type.MCGDB_MAIN_WINDOW:
      main_mc_window_fd=fd
    elif entity['type']==window_type.MCGDB_SOURCE_WINDOW:
      mc_windows_fds.append(fd)
  exec_in_main_pythread(update_FP,())
  if main_mc_window_fd!=None:
    cmd_for_main_window=''
    if not FP.fnew:
      #Новый файл отсутствует. Возможно исполнение
      #отлаживаемой программы завершилось. Необходимо убрать
      #позицию исполнения(отмеченную строку) в mcedit
      entities[main_mc_window_fd]['filename']=None
      if FP.lold:
        cmd_for_main_window+='unmark:{line};'.format(line=FP.lold)
        cmd_for_main_window+='set_curline:{curline};'.format(curline=-1)
      if FP.fold:
        #Если в редакторе был открыт файл, то закрываем его
        #если же файл не был открыт, и будет сделано fclose, то
        #редактор попросту закроется
        cmd_for_main_window+='fclose:;'
        entities[main_mc_window_fd]['filename_in_editor']=None
    if FP.fnew and (FP.fnew!=FP.fold or FP.force_reopen):
      #нужно открыть новый или переоткрыть существующий
      if FP.lold:
        cmd_for_main_window+='unmark:{line};'.format(line=FP.lold)
      if FP.fold:
        cmd_for_main_window+='fclose:;'
      cmd_for_main_window+='fopen:{fname},{line};'.format(fname=FP.fnew,line=FP.lnew)
      entities[main_mc_window_fd]['filename_in_editor']=FP.fnew
      cmd_for_main_window+='set_curline:{curline};'.format(curline=FP.lnew)
      entities[main_mc_window_fd]['filename']=FP.fnew
      cmd_for_main_window+=get_cmd_insert_bp_all(FP.fnew)
      cmd_for_main_window+='goto:{line};'.format(line=FP.lnew)
      cmd_for_main_window+='unmark_all:;' #Нужно очищать bookmark сразу после открытия файла,
      #поскольку может быть ситуация, когда редактор мог быть закрыт не из gdb.
      #И при закрытии mcedit может запомнить bookmark. И при повторном открытии файла
      #будет лишняя отмеченная строка.
      cmd_for_main_window+='mark:{line};'.format(line=FP.lnew)
    elif FP.lnew and FP.lnew!=FP.lold:
      #файл исполнения сотался тот же, строка исполнения поменялась
      if FP.lold:
        cmd_for_main_window+='unmark:{line};'.format(line=FP.lold)
      cmd_for_main_window+='set_curline:{curline};'.format(curline=FP.lnew)
      cmd_for_main_window+='mark:{line};'.format(line=FP.lnew)
      cmd_for_main_window+='goto:{line};'.format(line=FP.lnew)
    if cmd_for_main_window and cmd_for_main_window!='':
      if DebugPrint.mcgdb_communicate_protocol in verbose:
        gdb_print('commands for main: {}\n'.format(cmd_for_main_window))
      send_cmd(main_mc_window_fd,cmd_for_main_window)
  for fd in mc_windows_fds:
    pass


def cmd_terminate_event_loop(entities,fd,cmds):
  if DebugPrint.called in verbose:
    gdb_print('called cmd_terminate_event_loop\n')
  sys.exit(0)

def cmd_update_breakpoints(entities,fd,cmds):
  bps=gdb_bps=exec_in_main_pythread( gdb.breakpoints, ())
  bps_loc=[]
  for bp in bps:
    if not bp_in_queue(bp):
      #Возможно в очереди есть request на удаление этой точки
      bps_loc.append( get_bp_location(bp) )
  for bp_request in breakpoint_queue:
    rtype=bp_request[0]
    if rtype=='insert':
      bps_loc.append( [bp_request[1]] ) #append [ (filename,line) ]
  for entity_fd in entities:
    entity=entities[entity_fd]
    if entity['type'] not in (window_type.MCGDB_MAIN_WINDOW,window_type.MCGDB_SOURCE_WINDOW):
      continue
    entity_fname=entity['filename']
    if entity_fname==None:
      continue
    cmd=''
    for bp_locations in bps_loc:
      for loc_fname,loc_line in bp_locations:
        if loc_fname==entity_fname:
          cmd+='insert_bp:{line};'.format(line=loc_line)
    cmd='remove_bp_all:;'+cmd
    send_cmd(entity_fd,cmd)


def cmd_process_event_stop(entities,fd,args):
  process_breakpoint_queue()
  cmd_check_frame(entities,fd,args)

def cmd_process_event_exited(entities,fd,args):
  process_breakpoint_queue()
  cmd_inferior_exited(entities,fd,args)

def cmd_color_curline(entities,fd,args):
  for entity_fd in entities:
    entity=entities[entity_fd]
    if entity['type'] == window_type.MCGDB_MAIN_WINDOW:
      cmd='color_curline:{},{};'.format(args[0],args[1])
      send_cmd(entity_fd,cmd)

def exec_cmd_in_gdb(cmd):
  try:
    exec_in_main_pythread( gdb.execute, (cmd,False) )
  except gdb.error:
    pass


def cmd_enabledisable_breakpoint(entities,fd,args):
  pass
def cmd_next(entities,fd,args):
  exec_cmd_in_gdb("next")
def cmd_step(entities,fd,args):
  exec_cmd_in_gdb("step")
def cmd_until(entities,fd,args):
  exec_cmd_in_gdb("until")
def cmd_continue(entities,fd,args):
  exec_cmd_in_gdb("continue")


def process_command_from_gdb(entities,fd):
  cmds={
    'mcgdb_main_window':    cmd_mcgdb_main_window,
    'mcgdb_source_window':  cmd_mcgdb_source_window,
    'check_frame':          cmd_check_frame,
    'terminate':            cmd_terminate_event_loop,
    'inferior_exited':      cmd_inferior_exited,
    #'need_processing_bp':   cmd_need_processing_bp,
    'event_stop':           cmd_process_event_stop,
    'event_exited':         cmd_process_event_exited,
    'update_breakpoints':   cmd_update_breakpoints,
    window_type.MCGDB_BACKTRACE_WINDOW: cmd_mcgdb_backtrace_window,
    'color_curline':        cmd_color_curline,
  }
  return fetch_and_process_command(entities,fd,cmds)

def process_command_from_mc(entities,fd):
  cmds={
    'mouse_click'       :   cmd_mouse_click,
    'gdbcmd_breakpoint' :   cmd_insert_or_delete_breakpoint,
    'gdbcmd_enabledisable_breakpoint'   :   cmd_enabledisable_breakpoint,
    'gdbcmd_next'       :   cmd_next,
    'gdbcmd_step'       :   cmd_step,
    'gdbcmd_until'      :   cmd_until,
    'gdbcmd_continue'   :   cmd_continue,
  }
  return fetch_and_process_command(entities,fd,cmds)

def process_commant_from_btmc(entities,fd):
  #backtrace window
  gdb_print( recv_cmd(fd) )

def new_connection(entities,fd):
  actions={
    window_type.MCGDB_MAIN_WINDOW:  process_command_from_mc,
    window_type.MCGDB_SOURCE_WINDOW:process_command_from_mc,
    window_type.MCGDB_BACKTRACE_WINDOW:  process_commant_from_btmc,
  }
  lsock=entities[fd]['sock']
  conn,addr=lsock.accept()
  wt=window_queue.pop(0)
  filename=None
  cmd=''
  cmd+='set_window_type:{};'.format(wt['type'])
  if wt['type'] in (window_type.MCGDB_MAIN_WINDOW,window_type.MCGDB_SOURCE_WINDOW):
    cmd+='show_line_numbers:;'
    if wt['type']==window_type.MCGDB_MAIN_WINDOW:
      filename=FP.fnew
      line=FP.lnew
    elif wt['type']==window_type.MCGDB_SOURCE_WINDOW:
      filename=wt['filename']
      line=wt['line']
    if filename:
      cmd+='fopen:{fname},{line};'.format(
        fname=filename,
        line=line
      )
      cmd+=get_cmd_insert_bp_all(filename)
      cmd+='unmark_all:;'
      if FP.fnew==filename:
        cmd+='mark:{line};'.format(line=FP.lnew)
        cmd+='goto:{line};'.format(line=FP.lnew)
        cmd+='set_curline:{curline};'.format(curline=FP.lnew)
  newfd=conn.fileno()
  send_cmd(newfd,cmd)
  entities[newfd]={
      'type':wt['type'],
      'sock':conn,
      'action':actions[wt['type']],
      'filename_in_editor':filename,
  }
  entities[newfd]['filename']=filename
  if DebugPrint.new_worker in verbose:
    gdb_print("new worker type:{}\n".format(wt['type']))


def event_loop(lsock,local_r_fd):
  global entities
  listen_fd=lsock.fileno()
  rfds=[listen_fd,local_r_fd]
  entities={
    listen_fd:  {'type':'listen_fd',  'action':new_connection, 'sock':lsock},
    local_r_fd: {'type':'local_r_fd', 'action':process_command_from_gdb},
  }
  while True:
    rfds=entities.keys()
    #print rfds
    if len(rfds)==0:
      #nothing to be doing
      gdb_print('nothing tobe doing\n')
      break
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
      callback=entities[fd]['action']
      try:
        callback(entities,fd)
#      except SystemExit:
#        raise
      except CommandReadFailure:
        gdb_print('connection type={} was closed\n'.format(entities[fd]['type']))
        entities.pop(fd)
  gdb_print('event_loop stopped\n')

def stop_event_loop():
  global event_thread
  if event_thread:
    command='terminate:;'
    send_cmd(local_w_fd,command)
    #event_thread.join()
    event_thread=None

def get_gdb_version():
  try:
    s=gdb.execute('show version',False,True)
    major,minor=re.compile(r"GNU gdb \(GDB\) (\d+).(\d+)",re.MULTILINE).search(s).groups()
    ver=(int(major),int(minor))
    return ver
  except:
    return (None,None)

def is_gdb_version_correct():
  good_major=7
  good_minor=12
  major,minor=get_gdb_version()
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


def mc():
  global local_w_fd,event_thread,gdb_listen_port,main_thread_ident, __mcgdb_initialized
  if __mcgdb_initialized:
    #already initizlized
    return
  if not is_gdb_version_correct():
    return
  lsock=socket.socket()
  lsock.bind( ('',0) )
  port=lsock.getsockname()[1]
  gdb_listen_port=port
  lsock.listen(1)
  main_thread_ident=threading.current_thread().ident
  gdb.execute('echo gdb listen port:{}\n'.format(port))
  local_r_fd,local_w_fd=os.pipe()
  event_thread=threading.Thread(target=event_loop,args=(lsock,local_r_fd))
  event_thread.start()
  gdb.execute('set pagination off',False,False)
  gdb.execute('source {}'.format(PATH_TO_DEFINES_MCGDB))
  gdb.events.stop.connect(          lambda x:           notify_event_stop() )
  gdb.events.exited.connect(        lambda exit_code:   notify_event_exited(exit_code) )
  gdb.events.new_objfile.connect(   lambda x:           notify_event_new_objfile(x) )
  #gdb.events.breakpoint_created.connect( lambda bp : process_bp(bp,'created') )
  #gdb.events.breakpoint_deleted.connect( lambda bp : process_bp(bp,'deleted') )
  gdb.events.breakpoint_created.connect( lambda bp : notify_update_breakpoints() )
  gdb.events.breakpoint_deleted.connect( lambda bp : notify_update_breakpoints() )
  __mcgdb_initialized=True
  check_frame()
  #cmd_check_frame([],None,[])
  #gdb.events.exited.connect(stop_event_loop)


def notify_event_stop():            send_cmd(local_w_fd, 'event_stop:;')
def notify_event_exited(exit_code): send_cmd(local_w_fd, 'event_exited:{exit_code};')
def notify_update_breakpoints():    send_cmd(local_w_fd, 'update_breakpoints:;')
def notify_event_new_objfile(x):    check_frame()

def check_frame():
  #Данную команду нужно вызывать из hookpost-{up,down,frame,step,continue}
  command='check_frame:;'
  send_cmd(local_w_fd,command)

def inferior_exited(exit_code):
  command='inferior_exited:{exit_code};'.format(exit_code=exit_code)
  send_cmd(local_w_fd,command)

def mcgdb_main_window():
  if not __mcgdb_initialized:
    mc()
  command='mcgdb_main_window:;'
  send_cmd(local_w_fd,command)
  check_frame()

def mcgdb_source_window(filename,line=0):
  if not __mcgdb_initialized:
    gdb_print('ERROR: mcgdb not initialized\n')
    return
  command='mcgdb_source_window:{fname},{line};'.format(fname=filename,line=line)
  send_cmd(local_w_fd,command)


def mcgdb_backtrace_window():
  if not __mcgdb_initialized:
    gdb_print('ERROR: mcgdb not initialized\n')
    return
  command='{}:;'.format(window_type.MCGDB_BACKTRACE_WINDOW)
  send_cmd(local_w_fd,command)


def mcgdb_color_curline(text_color,background_color):
  command='color_curline:{},{};'.format(text_color,background_color)
  send_cmd(local_w_fd,command)


class McgdbCompleter (gdb.Command):
  def __init__ (self):
    super (McgdbCompleter, self).__init__ ("mcgdb", gdb.COMMAND_USER, gdb.COMPLETE_COMMAND, True)
McgdbCompleter()

class MainWindow (gdb.Command):
  """Open mcgdb main window with current source file and current execute line"""

  def __init__ (self):
    super (MainWindow, self).__init__ ("mcgdb mainwindow", gdb.COMMAND_USER, gdb.COMPLETE_COMMAND, True)

  def invoke (self, arg, from_tty):
    mcgdb_main_window()

MainWindow()

class CurlineColor (gdb.Command):
  """set color of current execute line. USAGE: mcgab curlinecolor textcolor backgroundcolor"""
  USAGE="USAGE: mcgab curlinecolor textcolor backgroundcolor"
  def __init__ (self):
    super (CurlineColor, self).__init__ ("mcgdb curlinecolor", gdb.COMMAND_USER, gdb.COMPLETE_COMMAND, True)

  def invoke (self, arg, from_tty):
    colors=arg.split()
    if len(colors)!=2:
      print self.USAGE
    text_color=colors[0]
    background_color=colors[1]
    mcgdb_color_curline(text_color,background_color)

CurlineColor()