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
  main_mc_window = "main_mc_window"
  mc_window      = "mc_window"


gdb_listen_port=None
stop_event_loop_flag=False
local_w_fd=None #В этот дескриптор можно писать команды из gdb
event_thread=None #данный поток обрабатывает команды из окон с mcedit и из gdb
PATH_TO_MC="~/bin/mcedit"
window_queue=[]

FP={
  'filename':   None,
  'line':       None,
}

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
    b=os.read(fd,1)
    if b==';':
      break
    if len(b)==0:
      raise CommandReadFailure
    data+=b
  sp=data.split(':')
  cmd=sp[0]
  args=sp[1].split(',')
  return (cmd,args)

def cmd_mouse_click(entities,fd,args):
  gdb.post_event(lambda : gdb.execute("echo mouse click in mc\n"))

def cmd_open_main_mc(entities,fd,args):
  window_queue.append(window_type.main_window_mc)
  gdb_print("echo open main mc command\n")
  os.system('gnome-terminal -e "{path_to_mc} --gdb-port={gdb_port}"'.format(
    path_to_mc=PATH_TO_MC,gdb_port=gdb_listen_port))

def cmd_open_mc(entities,fd,args):
  window_queue.append(window_type.window_mc)
  gdb_print("echo open mc command\n")

def fetch_and_process_command(entities,fd,cmds):
  cmd,args=recv_cmd(fd)
  try:
    callback=cmds[cmd]
  except KeyError:
    gdb.post_event(lambda : gdb.execute("echo bad command: `{}`\n".format(cmd)))
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


def process_file_location():
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
    return
  msg=''
  if FP['filename']!=filename:
    if FP['filename']!=None:
      msg+='fclose:;'
    msg+='fopen:{filename},{line};'.format(
      filename=filename,
      line=line,
    )
    msg+='mark:{line};'.format(line=line)
  elif FP['line']!=line:
    msg+='goto:{line};'.format(line=line)
    if FP['line']:
      msg+='unmark:{line};'.format(line=FP['line'])
    msg+='mark:{line};'.format(line=line)
  FP['filename']=filename
  FP['line']=line
  if msg!='':
    return msg
  else:
    return None


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
    if entity['type']=='main_window_mc':
      main_mc_window_fd=fd
    elif entity['type']=='mc_window':
      mc_windows_fds.append(fd)
  if main_mc_window_fd!=None:
    gdb_print('THIS\n')
    msgs=exec_in_main_pythread(process_file_location,())
    gdb_print('MESSAGES {}\n'.format(msgs))
    if msgs and msgs!='':
      os.write(main_mc_window_fd,msgs)
  for fd in mc_windows_fds:
    pass


def cmd_terminate_event_loop(entities,fd,cmds):
  gdb.post_event(lambda : gdb.execute('echo event loop stopped\n'))
  sys.exit(0)

def process_command_from_gdb(entities,fd):
  cmds={
    'open_main_mc': cmd_open_main_mc,
    'open_mc':      cmd_open_mc,
    'check_frame':  cmd_check_frame,
    'terminate':    cmd_terminate_event_loop,
  }
  return fetch_and_process_command(entities,fd,cmds)

def process_command_from_mc(entities,fd):
  cmds={
    'mouse_click':  cmd_mouse_click,
  }
  return fetch_and_process_command(entities,fd,cmds)


def new_connection(entities,fd):
  actions={
    'main_window_mc':process_command_from_mc,
  }
  lsock=entities[fd]['sock']
  conn,addr=lsock.accept()
  cmd,args=recv_cmd(conn.fileno())
  if len(args)==0:
    gdb.post_event(lambda : \
      gdb.execute("echo bad args received in `new_connection`\nconnection discard\n args:{}\n".format(args)))
    return
  if cmd=='worker_type':
    wtype=args[0]
    if wtype not in ('main_window_mc',):
      gdb.post_event(lambda : \
        gdb.execute("echo bad args received in `new_connection`\nconnection discard\n args:{}\n".format(args)))
      return
    entities[conn.fileno()]={
      'type':wtype,
      'sock':conn,
      'action':actions[wtype]
    }
    gdb.post_event(lambda : gdb.execute("echo new worker type:{}\n".format(wtype)))
  else:
    gdb.post_event(lambda : \
      gdb.execute("echo bad cmd received in `new_connection`\nconnection discard\n cmd:{}\n".format(cmd)))

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
  port=get_available_port()
  gdb_listen_port=port
  lsock=socket.socket()
  lsock.bind( ('',port) )
  lsock.listen(1)
  gdb.execute('echo gdb listen port:{}\n'.format(port))
  local_r_fd,local_w_fd=os.pipe()
  event_thread=threading.Thread(target=event_loop,args=(lsock,local_r_fd))
  event_thread.start()
  gdb.execute('source defines-mcgdb.gdb')
  gdb.events.stop.connect( lambda x:check_frame() )
  #gdb.events.exited.connect(stop_event_loop)

def check_frame():
  #Данную команду нужно вызывать из hookpost-{up,down,frame,step,continue}
  command='check_frame:;'
  os.write(local_w_fd,command)

def open_main_mc():
  command='open_main_mc:;'
  os.write(local_w_fd,command)

def open_mc(filename):
  command='open_mc:{fname};'.format(fname=filename)
  os.write(local_w_fd,command)





