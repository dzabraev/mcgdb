#coding=utf8
import gdb
import threading
import socket
import select
import os
import sys
import re
import errno

class window_type:
  MCGDB_MAIN_WINDOW     = "mcgdb_main_window"
  MCGDB_SOURCE_WINDOW   = "mcgdb_source_window"


gdb_listen_port=None
stop_event_loop_flag=False
local_w_fd=None #В этот дескриптор можно писать команды из gdb
event_thread=None #данный поток обрабатывает команды из окон с mcedit и из gdb
PATH_TO_MC="/home/dza/bin/mcedit"
PATH_TO_DEFINES_MCGDB="~/bin/defines-mcgdb.gdb"
window_queue=[]

class DebugPrint(object):
  called=1
  new_worker=2
  mcgdb_communicate_protocol=3

verbose=[
  #DebugPrint.mcgdb_communicate_protocol,
] # Данный массив используется для регулирования
#отладочного вывода. Данный массив должен заполняться
# свойствами класса DebugPrint
#example: verbose=[DebugPrint.called,DebugPrint.new_worker]

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
  disable_mcgdb_prefix=kwargs.get('mcgdb_prefix',False)
  mcgdb_prefix='' if disable_mcgdb_prefix else 'mcgdb:'
  if msg[-1]=='\n':
   msg=msg[:-1]
  msg='\n{mcgdb_prefix} {origmsg}\n{prompt}'.format(
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
  return (cmd,args)

def get_bp_location(bp):
  location=bp.location
  locs=exec_in_main_pythread(gdb.decode_line, (location,))[1]
  locations=[]
  if locs:
    for loc in locs:
      line=int(loc.line)
      filename=loc.symtab.filename
      locations.append( (filename,line) )
  return locations



def get_bp(gdb_bps,filename,line):
  for bp in gdb_bps:
    locations=get_bp_location(bp)
    for lf,ll in locations: #TODO lf=main.c filename=/home/dza/source/mcgdb/tests/main.c
      #gdb_print('{} {} {} {}\n'.format(ll,line,lf,filename))
      if lf==filename and ll==line:
        return bp
  return None

def cmd_mouse_click(entities,fd,args):
  filename=args[0] #in this file user produce click
  col  = int(args[1])
  line = int(args[2])
  click_types = args[3].split('|')
  #gdb_print("mouse click in mc col={} line={} types={}\n".format(col,line,click_types))
  if 'GPM_DOWN' in click_types and col<=6:
    #do breakpoint
    #gdb_print("mouse click in mc col={} line={} types={}\n".format(col,line,click_types))
    gdb_bps=exec_in_main_pythread( gdb.breakpoints, ())
    bp=get_bp(gdb_bps,filename,line)
    if bp!=None:
      #exists bp at (filename,line)
      exec_in_main_pythread( bp.delete, ())
    else:
      #create breakpoint
      exec_in_main_pythread( gdb.Breakpoint, ('{}:{}'.format(filename,line),)   )


def cmd_mcgdb_main_window(entities,fd,args):
  #chech whether main_window exists
  for entity_fd in entities:
    entity=entities[entity_fd]
    if entity['type']==window_type.MCGDB_MAIN_WINDOW:
      gdb_print('main window already exists\n')
      return
  window_queue.append({
    'type':window_type.MCGDB_MAIN_WINDOW,
  })
  if DebugPrint.called in verbose:
    gdb_print("called cmd_mcgdb_main_window\n")
  os.system('gnome-terminal -e "{path_to_mc} --gdb-port={gdb_port}"'.format(
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
    __exec_in_main_pythread_result=func(*args)
  except Exception as ex:
    __exec_in_main_pythread_result=None
    evt.set()
    raise
  evt.set()

def exec_in_main_pythread(func,args):
  #Данную функцию нельзя вызывать более чем из одного потока
  global __exec_in_main_pythread_result
  evt=threading.Event()
  gdb.post_event(
    lambda : __exec_in_main_pythread(func,args,evt)
  )
  evt.wait()
  return __exec_in_main_pythread_result


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
  try:
    frame=gdb.selected_frame ()
    filename=frame.find_sal().symtab.filename
    filename=get_abspath(filename)
    line=frame.find_sal().line-1
  except: #gdb.error:
    #no frame selected or maybe inferior exited?
    filename=None
    line=None
  FP.fold=FP.fnew
  FP.fnew=filename
  FP.lold=FP.lnew
  FP.lnew=line

def cmd_inferior_exited(entities,fd,args):
  #exit_code=args[0]
  cmd_check_frame(entities,fd,[])

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
      if FP.lold:
        cmd_for_main_window+='unmark:{line};'.format(line=FP.lold)
      if FP.fold:
        cmd_for_main_window+='fclose:;'
    if FP.fnew and FP.fnew!=FP.fold:
      if FP.lold:
        cmd_for_main_window+='unmark:{line};'.format(line=FP.lold)
      if FP.fold:
        cmd_for_main_window+='fclose:;'
      cmd_for_main_window+='fopen:{fname},{line};'.format(fname=FP.fnew,line=FP.lnew)
      cmd_for_main_window+='goto:{line};'.format(line=FP.lnew)
      cmd_for_main_window+='unmark_all:;' #Нужно очищать bookmark сразу после открытия файла,
      #поскольку может быть ситуация, когда редактор мог быть закрыт не из gdb.
      #И при закрытии mcedit может запомнить bookmark. И при повторном открытии файла
      #будет лишняя отмеченная строка.
      cmd_for_main_window+='mark:{line};'.format(line=FP.lnew)
    elif FP.lnew and FP.lnew!=FP.lold:
      if FP.lold:
        cmd_for_main_window+='unmark:{line};'.format(line=FP.lold)
      cmd_for_main_window+='mark:{line};'.format(line=FP.lnew)
      cmd_for_main_window+='goto:{line};'.format(line=FP.lnew)
    if cmd_for_main_window and cmd_for_main_window!='':
      if DebugPrint.mcgdb_communicate_protocol in verbose:
        gdb_print('commands for main: {}\n'.format(cmd_for_main_window))
      os.write(main_mc_window_fd,cmd_for_main_window)
  for fd in mc_windows_fds:
    pass


def cmd_terminate_event_loop(entities,fd,cmds):
  if DebugPrint.called in verbose:
    gdb_print('called cmd_terminate_event_loop\n')
  sys.exit(0)

def process_command_from_gdb(entities,fd):
  cmds={
    'mcgdb_main_window':    cmd_mcgdb_main_window,
    'mcgdb_source_window':  cmd_mcgdb_source_window,
    'check_frame':          cmd_check_frame,
    'terminate':            cmd_terminate_event_loop,
    'inferior_exited':      cmd_inferior_exited,
  }
  return fetch_and_process_command(entities,fd,cmds)

def process_command_from_mc(entities,fd):
  cmds={
    'mouse_click':  cmd_mouse_click,
  }
  return fetch_and_process_command(entities,fd,cmds)


def new_connection(entities,fd):
  actions={
    window_type.MCGDB_MAIN_WINDOW:  process_command_from_mc,
    window_type.MCGDB_SOURCE_WINDOW:process_command_from_mc,
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
    cmd+='unmark_all:;'
    if FP.fnew==filename:
      cmd+='mark:{line};'.format(line=FP.lnew)
      cmd+='goto:{line};'.format(line=FP.lnew)
  newfd=conn.fileno()
  os.write(newfd,cmd)
  entities[newfd]={
      'type':wt['type'],
      'sock':conn,
      'action':actions[wt['type']]
  }
  if DebugPrint.new_worker in verbose:
    gdb_print("new worker type:{}\n".format(wt['type']))


def event_loop(lsock,local_r_fd):
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
      return
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
      except SystemExit:
        raise
      except CommandReadFailure:
        #if read return 0 => connection was closed.
        entities.pop(fd)
      except:
        #something is bad
        raise #debug
  gdb_print('event_loop stopped\n')

def stop_event_loop():
  global event_thread
  if event_thread:
    command='terminate:;'
    os.write(local_w_fd,command)
    #event_thread.join()
    event_thread=None

def mc():
  global local_w_fd,event_thread,gdb_listen_port
  lsock=socket.socket()
  lsock.bind( ('',0) )
  port=lsock.getsockname()[1]
  gdb_listen_port=port
  lsock.listen(1)
  gdb.execute('echo gdb listen port:{}\n'.format(port))
  local_r_fd,local_w_fd=os.pipe()
  event_thread=threading.Thread(target=event_loop,args=(lsock,local_r_fd))
  event_thread.start()
  gdb.execute('source {}'.format(PATH_TO_DEFINES_MCGDB))
  gdb.events.stop.connect( lambda x: check_frame() )
  gdb.events.exited.connect(lambda exit_code: inferior_exited(exit_code) )
  #gdb.events.exited.connect(stop_event_loop)

def check_frame():
  #Данную команду нужно вызывать из hookpost-{up,down,frame,step,continue}
  command='check_frame:;'
  os.write(local_w_fd,command)

def inferior_exited(exit_code):
  command='inferior_exited:{exit_code};'.format(exit_code=exit_code)
  os.write(local_w_fd,command)

def mcgdb_main_window():
  command='mcgdb_main_window:;'
  os.write(local_w_fd,command)

def mcgdb_source_window(filename,line=0):
  command='mcgdb_source_window:{fname},{line};'.format(fname=filename,line=line)
  os.write(local_w_fd,command)





