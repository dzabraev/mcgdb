#coding=utf8

from abc import abstractmethod, abstractproperty
import os,socket,ctypes,subprocess
import gdb

import mcgdb
from mcgdb.common import  pkgsend,pkgrecv,gdb_print,exec_cmd_in_gdb,gdb_stopped,\
                          error,get_prompt,debug,is_main_thread,exec_main




class BaseWin(object):
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
    if not hasattr(self,'subentities'):
      self.subentities={}
    #super(BaseWin,self).__init__(**kwargs)

  #@abstractproperty
  #def subentities(self):
  #  pass

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
    for subentity in self.subentities.values():
      subentity.process_connection()
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

  def send(self,msg):
    pkgsend(self.fd,msg)

  def recv(self):
    return pkgrecv(self.fd)

  def process_pkg(self,pkg):
    '''Обработать сообщение из графического окна, GDB, или класса, который
        соответствует графическому окну.

      В сущностях типа AuxWin и subentities типа RegistersTable допускается
      определять следующие методы для обработки событий. Данные методы будут вызываться
      автоматически.

      1. Методы для обработки событий из gdb
      gdbevt_cont(self,pkg)
      gdbevt_exited(self,pkg)
      gdbevt_stop(self,pkg)
      gdbevt_new_objfile(self,pkg)
      gdbevt_clear_objfiles(self,pkg)
      gdbevt_inferior_call_pre(self,pkg)
      gdbevt_inferior_call_post(self,pkg)
      gdbevt_memory_changed(self,pkg)
      gdbevt_register_changed(self,pkg)
      gdbevt_breakpoint_created(self,pkg)
      gdbevt_breakpoint_modified(self,pkg)
      gdbevt_breakpoint_deleted(self,pkg)

      2. Методы, которые будут вызываться, когда пользователь
          выполнил команду в shell'е. Назначение данных методов заключается в том, что
          GDB не генерирует события, при помощи которых представляется возможным отслеживать,
          например, изменение текущего фрейма или потока.
      shellcmd_bp_disable(self,pkg)
      shellcmd_bp_enable(self,pkg)
      shellcmd_frame(self,pkg)
      shellcmd_frame_up(self,pkg)
      shellcmd_frame_down(self,pkg)
      shellcmd_thread(self,pkg)

      3. Методы, которые используются для обработки событий,
      которые генерируются сущностями или подсущностями.
      mcgdbevt_frame(self,data)     Данное событие генерируется, при изменении текущего фрейма из Python API.
                                    При изменении из Python API события типа shellcmd генерироваться не будет.

      mcgdbevt_thread(self,data)    Данное событие генерируется, при изменении текущего потока из Python API.

      4. Пакеты типа onclick. Виджет типа wtable.c способен генерировать событие onclick. Для генерации события
      на кликабельный объект помещается пара "onclick_data":PKG. При клике по объекту PKG будет отправлен
      сущености. PKG должен удовлетворять структуре пакета, которая описана в п.5

      5. Принцип соответствия названия метода пакету. Каждый пакет, который будет доставляться до сущностей
      содержит, как минимум, следующие поля {'cmd':cmd_group, cmd_group:command }
      На основе данного пакета будет сформировано название метода method_name='{cmd_group}_{cmd}'.format(cmd_group=cmd_group,command=command)
      Если сущность обладает методом method_name, то данный метод будет вызван на сущности, при этом методу будет передан пакет pkg.

      Если пакет содержит поле subentity_dst, то будет вызвана только подсущность.

      Порядок вызова методов.
      Сначала метод вызывается у Entity, далее у subentities
    '''
    subentity_name=pkg.get('subentity_dst')
    destinations=[self]
    if subentity_name:
      destinations+=[self.subentities[subentity_name]]
    else:
      destinations+=self.subentities.values()
    cmd=pkg['cmd']
    cmd_name=pkg[cmd]
    method_name = '{}_{}'.format(cmd,cmd_name)
    ret_pkgs=[]
    for subsentity in destinations:
      if hasattr(subsentity,method_name):
        cb=getattr(subsentity,method_name)
        ret=cb(pkg)
        if ret:
          assert type(ret) in (list,tuple)
          ret_pkgs+=ret
    return ret_pkgs

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













