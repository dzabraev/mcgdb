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
verbose=0

class _FP(object):
  fnew=None
  fold=None
  lnew=None
  lold=None

FP=_FP()

class CommandReadFailure(Exception): pass
class StopEventThread(Exception): pass

def get_available_port():
  return 9091

def gdb_print(msg):
  #thread safe
  gdb.post_event(lambda : gdb.write(msg))

def recv_cmd(fd):
  data=''
  while True:
    try:
      b=os.read(fd,1)
    except IOError as e:
      if e.errno == errno.EINTR:
        continue
    if len(b)==0:
      raise CommandReadFailure
    if b==';':
      break
    data+=b
  sp=data.split(':')
  cmd=sp[0]
  args=sp[1].split(',')
  return (cmd,args)

def cmd_mouse_click(entities,fd,args):
  gdb_print("echo mouse click in mc\n")

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
  gdb_print("echo open main mc command\n")
  os.system('gnome-terminal -e "{path_to_mc} --gdb-port={gdb_port}"'.format(
    path_to_mc=PATH_TO_MC,gdb_port=gdb_listen_port))

def cmd_mcgdb_source_window(entities,fd,args):
  window_queue.append({
    'type':window_type.MCGDB_SOURCE_WINDOW,
    'filename':args[0],
    'line':args[1],
  })
  gdb_print("echo open mc command\n")

def fetch_and_process_command(entities,fd,cmds):
  cmd,args=recv_cmd(fd)
  try:
    callback=cmds[cmd]
  except KeyError:
    gdb_print("echo bad command: `{}`\n".format(cmd))
    return
  return callback(entities,fd,args)

__exec_in_main_pythread_result=None

def __exec_in_main_pythread(func,args,evt):
  global __exec_in_main_pythread_result
  try:
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
  except gdb.error:
    #no frame selected?
    return
  try:
    filename=frame.find_sal().symtab.filename
    filename=get_abspath(filename)
    line=frame.find_sal().line-1
  except gdb.exceptions.AttributeError:
    #maybe inferior exited
    filename=None
    line=None
  FP.fold=FP.fnew
  FP.fnew=filename
  FP.lold=FP.lnew
  FP.lnew=line


def cmd_check_frame(entities,fd,args):
  # Нужно изменить файл и/или позицию в файле
  # в main mc window. Если существует не main mc window,
  # и в нем открыт файл filename, то нужно подкрасить в нем
  # текущую строчку. При этом если существовало не main mc window,
  # в котором была подкрашена текущая строчка, то покраску с нее
  # необходимо снять.
  gdb.post_event(lambda : gdb.execute('echo check_frame called\n'))
  main_mc_window_fd=None
  mc_windows_fds=[]
  for fd in entities:
    entity=entities[fd]
    gdb_print('TYPE:`{}`\n'.format(entity['type']))
    if entity['type']==window_type.MCGDB_MAIN_WINDOW:
      main_mc_window_fd=fd
    elif entity['type']==window_type.MCGDB_SOURCE_WINDOW:
      mc_windows_fds.append(fd)
  exec_in_main_pythread(update_FP,())
  if main_mc_window_fd!=None:
    msg=''
    if FP.fnew and FP.fnew!=FP.fold:
      if FP.lold:
        msg+='unmark:{line};'.format(line=FP.lold)
      if FP.fold:
        msg+='fclose:;'
      msg+='fopen:{fname},{line};'.format(fname=FP.fnew,line=FP.lnew)
      msg+='mark:{line};'.format(line=FP.lnew)
    elif FP.lnew and FP.lnew!=FP.lold:
      if FP.lold:
        msg+='unmark:{line};'.format(line=FP.lold)
      msg+='mark:{line};'.format(line=FP.lnew)
      msg+='goto:{line};'.format(line=FP.lnew)
    gdb_print('MESSAGES {}\n'.format(msg))
    if msg and msg!='':
      os.write(main_mc_window_fd,msg)
  for fd in mc_windows_fds:
    pass


def cmd_terminate_event_loop(entities,fd,cmds):
  gdb.post_event(lambda : gdb.execute('echo event loop stopped\n'))
  sys.exit(0)

def process_command_from_gdb(entities,fd):
  cmds={
    'mcgdb_main_window':    cmd_mcgdb_main_window,
    'mcgdb_source_window':  cmd_mcgdb_source_window,
    'check_frame':          cmd_check_frame,
    'terminate':            cmd_terminate_event_loop,
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
  cmd='set_window_type:{};'.format(wt['type'])
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
  gdb_print("echo new worker type:{}\n".format(wt['type']))
  

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
  gdb.post_event(lambda : gdb.execute('echo event_loop stopped\n'))

def stop_event_loop():
  global event_thread
  if event_thread:
    command='terminate:;'
    os.write(local_w_fd,command)
    #event_thread.join()
    event_thread=None

def mc():
  global local_w_fd,event_thread,gdb_listen_port
  #port=get_available_port()
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
  gdb.events.stop.connect( lambda x:check_frame() )
  #gdb.events.exited.connect(stop_event_loop)

def check_frame():
  #Данную команду нужно вызывать из hookpost-{up,down,frame,step,continue}
  command='check_frame:;'
  os.write(local_w_fd,command)

def mcgdb_main_window():
  command='mcgdb_main_window:;'
  os.write(local_w_fd,command)

def mcgdb_source_window(filename,line=0):
  command='mcgdb_source_window:{fname},{line};'.format(fname=filename,line=line)
  os.write(local_w_fd,command)





