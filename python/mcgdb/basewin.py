#coding=utf8

from abc import abstractmethod, abstractproperty, ABCMeta
import os,socket,ctypes,subprocess,time,logging,json,distutils.spawn,sys
import gdb

import mcgdb
from mcgdb.common import  pkgsend,pkgrecv,gdb_print,exec_cmd_in_gdb,gdb_stopped,\
                          error,get_prompt,debug,is_main_thread,exec_main,\
                          mcgdbBaseException, TABID_TMP, gdbprint, VALGRIND, COREDUMP, USETERM, WAITGDB



class StorageId(object):
  def __init__(self,*args,**kwargs):
    self.id_exemplar_storage={}
    self.last_exemplar_id=1024
    super(StorageId,self).__init__(*args,**kwargs)

  def key_drop(self,key):
    if key in self.id_exemplar_storage:
      del self.id_exemplar_storage[key]

  def id_get(self,key):
    return self.id_exemplar_storage.get(key,(None,None))

  def id_insert(self,key,data):
    assert key not in self.id_exemplar_storage
    id=self.last_exemplar_id
    self.last_exemplar_id+=1
    self.id_exemplar_storage[key]=(id,data)
    return id

  def id_update(self,key,new_data):
    (id,data)=self.id_exemplar_storage[key]
    self.id_exemplar_storage[key] = (id,new_data)
    return idc




class CommunicationMixin(object):
  __metaclass__ = ABCMeta

  def __init__(self,*args,**kwargs):
    self.fd = kwargs.pop('communication_fd',None)
    super(CommunicationMixin,self).__init__(*args,**kwargs)

  def setup_communication_fd(self,fd):
    self.fd=fd

  def get_communication_fd(self):
    return self.fd

  def send(self,msg):
    assert self.fd!=None
    if msg is None:
      return
    logging.info('time={time} sender={type} pkgs={pkgs}'.format(type=(getattr(self,'type',None) or self.subentity_name),pkgs=json.dumps(msg),time=time.time()))
    pkgsend(self.fd,msg)

  def recv(self):
    assert self.fd!=None
    return pkgrecv(self.fd)

  def pkg_send_error(self,message):
    '''Вывести пользователю ошибку в граф. окне.'''
    return {'cmd':'error_message','message':message}

  def send_error(self,message):
    '''Вывести пользователю ошибку в граф. окне.'''
    try:
      self.send(self.pkg_send_error(message))
    except:
      pass

  def pkg_callback(self,callback_id,type):
    return {'cmd':'call_cb','callback_id':callback_id,'type':type}

  def send_pkg_callback(self,*args,**kwargs):
    return self.send(self.pkg_callback(*args,**kwargs))

class PkgMeta(ABCMeta):
  def __new__(meta, name, bases, dct):
    for name,val in dct.items():
      if name.startswith('pkg_'):
        fn = dct.pop(name)
        dct['send_'+name] = lambda self,*args,**kwargs : self.send(fn(self,*args,**kwargs))
    return super(PkgMeta, meta).__new__(meta,name,bases,dct)

class TablePackages(CommunicationMixin):
  __metaclass__ = PkgMeta

  @abstractproperty
  def subentity_name(self): pass

  @exec_main
  def get_thread_info(self):
    threads=[]
    for thread in gdb.selected_inferior().threads():
      if not thread.is_valid():
        continue
      pid,lwp,tid = thread.ptid
      threads.append({
        'name'        : thread.name,
        'num'         : thread.num,
        'global_num'  : thread.global_num,
        'pid'         : pid,
        'lwp'         : lwp,
        'tid'         : tid,
      })
    selected = gdb.selected_thread()
    return {
      'thread_list' : get_thread_list(),
      'selected_thread': selected.global_num if selected is not None else -1,
    }

  def pkg_update_threads(self):
    return {'cmd':'update_threads', 'info':self.get_thread_info()}


  def pkg_exemplar_set(self,id):
    return {'cmd':'exemplar_set','id':id,'table_name':self.subentity_name}

  def pkg_select_node(self,id,selected,visible=None):
    node_data={'id':id, 'selected':selected}
    if visible is not None:
      node_data['visible']=visible
    return self.pkg_update_nodes([node_data])

  def pkg_do_row_visible(self,nrow):
    return {'cmd':'do_row_visible','table_name':self.subentity_name, 'nrow':nrow}


  def pkg_exemplar_create(self,tabdata,id,set=True):
      pkg={ 'cmd':'exemplar_create',
            'table_name':self.subentity_name,
            'table':tabdata,
            'id':id,
            'set':set,
      }
      return pkg

  def pkg_update_nodes(self,need_update):
    return {'cmd':'update_nodes', 'table_name':self.subentity_name, 'nodes':need_update}

  def pkg_drop_nodes(self,ids):
    return {'cmd':'drop_nodes', 'table_name':self.subentity_name, 'ids':ids}

  def pkg_drop_rows(self,ids):
    return {'cmd':'drop_rows', 'table_name':self.subentity_name, 'ids':ids}

  def pkg_insert_rows(self,rows,rowid=None):
    ''' Добавить строки rows перед строкой с id=rowid. Если rowid is None, то строки будут добавляться за последнюю'''
    pkg={'cmd':'insert_rows','table_name':self.subentity_name,'rows':rows}
    if not rowid is None:
      pkg['rowid']=rowid
    return pkg

  def pkg_append_rows(self,rows):
    return self.pkg_insert_rows(rows)

  def pkg_transaction(self,pkgs):
    ''' Сначала будут выполнены команды из всхе пакетов. и только потом будет сделана перерисовка'''
    assert type(pkgs) is list
    pkgs=filter(lambda x:x is not None,pkgs)
    if pkgs:
      if not type(pkgs[0]) is dict:
        gdb_print('pkg='+str(pkgs[0])+'\n\n')
      assert type(pkgs[0]) is dict
      return {'cmd':'transaction','table_name':self.subentity_name,'pkgs':pkgs}

  def one_row_one_cell(self,msg):
    return {'rows':[{'columns':[{'chunks':[{'str':msg}]}]}]}

  def pkg_message_in_table(self,msg,id=TABID_TMP,set_current=True):
    pkg={
      'cmd':'exemplar_create',
      'table':self.one_row_one_cell(msg),
      'table_name':self.subentity_name,
      'id':id,
    }
    if set_current:
      pkg['set'] = set_current
    return pkg





class BaseWin(CommunicationMixin,StorageId):
  __metaclass__ = ABCMeta

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
    self.lsock=socket.socket()
    self.lsock.bind( ('',0) )
    self.lsock.listen(1)
    self.listen_port=self.lsock.getsockname()[1]
    self.listen_fd=self.lsock.fileno()
    manually=kwargs.pop('manually',False)
    cmd=self.make_runwin_cmd()
    self.subentities={}

    if manually:
      gdb_print('''Execute manually `{cmd}` for start window'''.format(cmd=cmd))
    else:
      gui_window_cmd = '{cmd}'
      if VALGRIND is not None:
        gui_window_cmd = 'valgrind --log-file={logprefix}_{type}.log {cmd}'.format(
          type=self.type,
          logprefix=VALGRIND,
          cmd=gui_window_cmd,
        )
      if COREDUMP:
        gui_window_cmd = 'bash -c "cd {COREDUMP}; ulimit -c unlimited; {cmd}"'.format(
          COREDUMP=COREDUMP,
          cmd=gui_window_cmd)
      xterm,xterm_abspath = self.get_term()
      gui_window_cmd='''{xterm} -e '{cmd1}' '''.format(cmd1=gui_window_cmd,xterm=xterm_abspath)
      complete_cmd=gui_window_cmd.format(cmd=cmd)
      proc=subprocess.Popen(complete_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      if xterm=='gnome-terminal':
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

  def get_term(self):
    if USETERM:
      term=USETERM
      abspath=distutils.spawn.find_executable(term)
      if abspath is None:
        gdb_print('ERROR: cant find terminal from USETERM=%s\n' % term)
        sys.exit(0)
      return term,abspath
    for term in ['gnome-terminal','xterm']:
      abspath = distutils.spawn.find_executable(term)
      if abspath:
        return term,abspath

  @abstractproperty
  def subentities_cls(self): pass


  @exec_main
  def init_subentities(self):
    for cls in self.subentities_cls:
      self.subentities[cls.subentity_name] = cls(communication_fd=self.get_communication_fd())

  def make_runwin_cmd(self):
    ''' Данный метод формирует shell-команду для запуска окна с editor.
        Команда формируется на основе self.listen_port
    '''
    cmd = '{path_to_mc} -e --gdb-port={gdb_port}'.format(
     path_to_mc=mcgdb.PATH_TO_MC,gdb_port=self.listen_port)
    if WAITGDB is not None:
      cmd += ' --wait-gdb'
    return cmd


  def byemsg(self):
    gdb_print("type `{cmd}` to restart {type}\n{prompt}".format(
      cmd=self.startcmd,type=self.type,prompt=get_prompt()))

  @exec_main
  def process_connection(self):
    '''Принять (accept) соединение от граф. окна.
    '''
    self.conn = self.lsock.accept()[0]
    self.lsock.close()
    self.lsock      =None
    self.listen_port=None
    self.listen_fd  =None
    self.setup_communication_fd(self.conn.fileno())
    self.send({
      'cmd' :'set_window_type',
      'type':self.type,
    })
    self.init_subentities()
    for subentity in self.subentities.values():
      subentity.process_connection()
    return True

  @abstractproperty
  def startcmd(self):
    pass


  @abstractproperty
  def type(self):
    pass


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
      shellcmd_up(self,pkg)
      shellcmd_down(self,pkg)
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
    err_occurs=False
    callback_id=pkg.get('callback_id')
    for subsentity in destinations:
      if hasattr(subsentity,method_name):
        cb=getattr(subsentity,method_name)
        try:
          ret=cb(pkg)
        except mcgdbBaseException as e:
          if callback_id is not None:
            self.send_pkg_callback(callback_id,type=1)
          self.send_error(str(e))
          ret=None
          err_occurs=True
        if ret:
          assert type(ret) in (list,tuple)
          ret_pkgs+=ret
    return ret_pkgs #send this packages to gdb entities

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









