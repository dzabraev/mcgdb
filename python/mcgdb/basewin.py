#coding=utf8

from abc import ABCMeta, abstractmethod, abstractproperty
import os,socket,ctypes,subprocess
import gdb

import mcgdb
from mcgdb.common import  pkgsend,pkgrecv,gdb_print,exec_cmd_in_gdb,gdb_stopped,\
                          error,get_prompt,debug,is_main_thread,exec_in_main_pythread


class BaseWin(object):

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

    mcgdb._dw[self.type]=self #debug
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
        gdb_print('''\nCan't open gui window({type}). execute manually: `{cmd}`\n'''.format(cmd=cmd,type=self.type))

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
     path_to_mc=mcgdb.PATH_TO_MC,gdb_port=self.listen_port)


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
  def startcmd(self):
    pass


  @abstractproperty
  def type(self):
    pass

  @abstractmethod
  def process_shellcmd(self,cmd):
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



def is_incomplete_type_ptr(value):
  return  value.type.strip_typedefs().code==gdb.TYPE_CODE_PTR and \
          value.type.strip_typedefs().target().strip_typedefs().code in (gdb.TYPE_CODE_STRUCT,gdb.TYPE_CODE_UNION) and \
          len(value.type.strip_typedefs().target().strip_typedefs().fields())==0

def valueaddress_to_ulong(value):
  if value==None:
    return None
  return ctypes.c_ulong(long(value)).value

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


