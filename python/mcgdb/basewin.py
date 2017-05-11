#coding=utf8

from abc import ABCMeta, abstractmethod, abstractproperty
import os,socket,ctypes,subprocess
import gdb

import mcgdb
from mcgdb.common import  pkgsend,pkgrecv,gdb_print,exec_cmd_in_gdb,gdb_stopped,\
                          error,get_prompt,debug,is_main_thread,exec_in_main_pythread



class StubEvents(object):
  def gdbevt_cont(self,evt):                pass
  def gdbevt_exited(self,evt):              pass
  def gdbevt_stop(self,evt):                pass
  def gdbevt_new_objfile(self,evt):         pass
  def gdbevt_clear_objfiles(self,evt):      pass
  def gdbevt_inferior_call_pre(self,evt):   pass
  def gdbevt_inferior_call_post(self,evt):  pass
  def gdbevt_memory_changed(self,evt):      pass
  def gdbevt_register_changed(self,evt):    pass
  def gdbevt_breakpoint_created(self,evt):  pass
  def gdbevt_breakpoint_modified(self,evt): pass
  def gdbevt_breakpoint_deleted(self,evt):  pass


  def shellcmd_quit(self):          pass
  def shellcmd_bp_disable(self):    pass
  def shellcmd_bp_enable(self):     pass
  def shellcmd_frame(self):         pass
  def shellcmd_frame_up(self):      pass
  def shellcmd_frame_down(self):    pass
  def shellcmd_thread(self):        pass

  def mcgdbevt_frame(self,data):    pass
  def mcgdbevt_thread(self,data):    pass


  def process_connection(self): pass

class BaseWin(StubEvents):
  def __init__(self, **kwargs):
    '''
        Args:
            **manually (bool): Если false, то команда для запуска граф. окна не будет выполняться.
                Вместе этого пользователю будет выведена команда, при помощи которой он сам должен
                запустить окно. Данную опцию нужно применять, когда нет возможности запустить граф. окно
                из gdb. Например, если зайти по ssh на удаленную машину, то не всегда есть возможность
                запустить gnome-terminal.

        При создании класса, в методе __init__ будет создан процесс, в котором будет запущено
        графическое окно. Данному окну будет передан порт, который прослушивается в gdb.
        Графическое окно будет устанавливать соединение с этим портом на адрес 127.0.0.1
        Данное соединение должно приниматься методом `process_connection`.
    '''
    if not hasattr(self,'window_event_handlers'):
      self.window_event_handlers={}
    base_window_event_handlers={
      'onclick_data'    : self.onclick_data,
      'shellcmd'        : self.process_shellcmd,
      'mcgdbevt'        : self.process_mcgdbevt,
      'exec_in_gdb'     : self.exec_in_gdb,
    }
    base_window_event_handlers.update(self.window_event_handlers)
    self.window_event_handlers=base_window_event_handlers

    if not hasattr(self,'gdb_event_cbs'):
      self.gdb_event_cbs={}
    gdb_event_cbs = {
      'cont'                :   self.gdbevt_cont,
      'exited'              :   self.gdbevt_exited,
      'stop'                :   self.gdbevt_stop,
      'new_objfile'         :   self.gdbevt_new_objfile,
      'clear_objfiles'      :   self.gdbevt_clear_objfiles,
      'inferior_call_pre'   :   self.gdbevt_inferior_call_pre,
      'inferior_call_post'  :   self.gdbevt_inferior_call_post,
      'memory_changed'      :   self.gdbevt_memory_changed,
      'register_changed'    :   self.gdbevt_register_changed,
      'breakpoint_created'  :   self.gdbevt_breakpoint_created,
      'breakpoint_modified' :   self.gdbevt_breakpoint_modified,
      'breakpoint_deleted'  :   self.gdbevt_breakpoint_deleted,
    }
    gdb_event_cbs.update(self.gdb_event_cbs)
    self.gdb_event_cbs = gdb_event_cbs


    if not hasattr(self,'shellcmd_cbs'):
      self.shellcmd_cbs={}
    shellcmd_cbs = {
      'quit'        : self.shellcmd_quit,
      'bp_disable'  : self.shellcmd_bp_disable,
      'bp_enable'   : self.shellcmd_bp_enable,
      'frame'       : self.shellcmd_frame,
      'frame_up'    : self.shellcmd_frame_up,
      'frame_down'  : self.shellcmd_frame_down,
      'thread'      : self.shellcmd_thread,
    }
    shellcmd_cbs.update(self.shellcmd_cbs)
    self.shellcmd_cbs = shellcmd_cbs

    if not hasattr(self,'click_cmd_cbs'):
      click_cmd_cbs={}

    if not hasattr(self,'mcgdbevt_cbs'):
      self.mcgdbevt_cbs={}
    mcgdbevt_cbs = {
      'frame'       : self.mcgdbevt_frame,
      'thread'      : self.mcgdbevt_thread,
    }
    mcgdbevt_cbs.update(self.mcgdbevt_cbs)
    self.mcgdbevt_cbs = mcgdbevt_cbs

    if not hasattr(self,'chunk_value_index'):
      self.chunk_value_index_cnt=0
      self.chunk_value_index={}

    if not hasattr(self,'cache_table_exemplar'):
      self.cache_table_exemplar={}
      self.cache_table_counter=0


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
    manually=kwargs.pop('manually',False)
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
    super(BaseWin,self).__init__(**kwargs)

  def _onclick_data(self,pkg):
    click_cmd = pkg['data']['click_cmd']
    cb=self.click_cmd_cbs.get(click_cmd)
    if cb==None:
      return
    return cb(pkg)

  def name_index(self,name):
    #gdb_print(name+'\n')
    idx=self.chunk_value_index.get(name)
    if idx!=None:
      return idx
    idx = self.chunk_value_index_cnt
    self.chunk_value_index_cnt+=1
    self.chunk_value_index[name]=idx
    return idx

  def insert_data(self,key,tabdata):
    old = self.cache_table_exemplar.get(key)
    if old==None:
      idx=self.cache_table_counter
      self.cache_table_counter+=1
    else:
      idx,_ = old
    self.cache_table_exemplar[key] = (idx,tabdata)
    return idx

  def get_data(self,key):
    cv=self.cache_table_exemplar.get((tabname,tabkey))
    if cv==None:
      return None,None
    else:
      return cv

  def exec_in_gdb(self,exec_cmd):
    if gdb_stopped():
      exec_cmd_in_gdb(exec_cmd)

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
    '''Принять (accept) соединение от граф. окна.
    '''
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

  def process_common(self,evttype,pkg):
    cmd=pkg[evttype]
    method=evttype+'_'+cmd
    rets=[]
      if hasattr(self,method):
        cb=getattr(self,method)
        ret=cb(self)
        if ret:
          rets.append(ret)
    for tabname,table in self.tables.items():
      if hasattr(table,method):
        cb=getattr(table,method)
        ret=cb(table)
        if ret:
          rets.append(ret)
    return rets

  def process_shellcmd(self,pkg):
    '''
      def shellcmd_quit(self):pass
      def shellcmd_bp_disable(self):pass
      def shellcmd_bp_enable(self):pass
      def shellcmd_frame(self):pass
      def shellcmd_frame_up(self):pass
      def shellcmd_frame_down(self): pass
      def shellcmd_thread(self):pass
    '''
    return self.process_common(self,'shellcmd',pkg)

  def process_mcgdbevt(self,pkg):
    '''
      def mcgdbevt_frame(self,data):pass
      def mcgdbevt_thread(self,data):pass
    '''
    return self.process_common(self,'mcgdbevt',pkg)

  def onclick(self,pkg):
    '''
        onclick_change_variab,
        onclick_change_slice,
        onclick_expand_variable,
        onclick_collapse_variable
    '''
    table = self.tables[pkg['tabname']]
    method = 'onclick_'+pkg['onclick']
    return getattr(table,method)(pkg['onclick_data'])

  def process_gdbevt(self,name,evt):
    '''
      Если в таблице или дочернем классе будет определена одна из этих функций,
      то она будет вызвана автоматически при получении события
      def gdbevt_cont(self,evt):pass
      def gdbevt_exited(self,evt):pass
      def gdbevt_stop(self,evt):pass
      def gdbevt_new_objfile(self,evt):pass
      def gdbevt_clear_objfiles(self,evt):pass
      def gdbevt_inferior_call_pre(self,evt):pass
      def gdbevt_inferior_call_post(self,evt):pass
      def gdbevt_memory_changed(self,evt):pass
      def gdbevt_register_changed(self,evt):pass
      def gdbevt_breakpoint_created(self,evt):pass
      def gdbevt_breakpoint_modified(self,evt):pass
      def gdbevt_breakpoint_deleted(self,evt):pass
    '''
    return self.process_common(self,'gdbevt',pkg)


  def send(self,msg):
    pkgsend(self.fd,msg)

  def recv(self):
    return pkgrecv(self.fd)

  def process_pkg(self,pkg=None):
    '''Обработать сообщение из графического окна или от другой сущности'''
    if pkg==None:
      pkg=self.recv()
    cmd=pkg['cmd']
    cb=self.window_event_handlers[cmd]
    return cb(pkg)

  def terminate(self):
    try:
      self.send({'cmd':'exit'})
    except:
      pass

  @exec_main
  def get_current_position(self):
    '''Возвращает текущую позицию исполнения.

        return:
        (filename,line)
    '''
    try:
      frame=gdb.selected_frame ()
      filename=frame.find_sal().symtab.fullname()
      line=frame.find_sal().line-1
    except: #gdb.error:
      #no frame selected or maybe inferior exited?
      filename=None
      line=None
    return filename,line

  def send_error(self,message):
    '''Вывести пользователю ошибку в граф. окне.
    '''
    try:
      self.send({'cmd':'error_message','message':message})
    except:
      pass













