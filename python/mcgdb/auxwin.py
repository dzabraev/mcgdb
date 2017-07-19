#coding=utf8

import gdb

import re,sys,ctypes
import traceback


from mcgdb.basewin import BaseWin, StorageId, CommunicationMixin

from mcgdb.valuetochunks import check_chunks, ValueToChunks, get_frame_funcname, \
                                get_frame_fileline, get_frame_func_args, frame_func_args

from mcgdb.common  import exec_main, valcache, INDEX, INDEX_tmp, \
                    get_this_thread_num, mcgdbBaseException, mcgdbChangevarErr, \
                    gdb_stopped,inferior_alive,gdb_print, TablePackages,TABID_TMP, \
                    TablePackages


from abc import ABCMeta, abstractmethod, abstractproperty

class ValuesExemplar(object):
  __metaclass__ = ABCMeta

  def __init__(self,subentity_name,*args,**kwargs):
    self.subentity_name = subentity_name
    super(ValuesExemplar,self).__init__(*args,**kwargs)

  @abstractmethod
  def get_table(self):
    ''' Return whole table for current inferior state'''
    raise NotImplementedError

  @abstractmethod
  def need_update(self):
    ''' This function compare saved inferior state with
        current inferior state and produce packages, that
        will be update GUI window'''
    raise NotImplementedError


class BaseSubentity(TablePackages, CommunicationMixin):
  __metaclass__ = ABCMeta

  @exec_main
  def __init__(self,**kwargs):
    self.setup_communication_fd(kwargs.pop('communication_fd'))
    super(BaseSubentity,self).__init__(**kwargs)

  @abstractproperty
  def subentity_name(self):raise NotImplementedError

  def clear_table(self):
    self.send_pkg_message_in_table ('')



class SubentityUpdate(BaseSubentity,StorageId,CommunicationMixin):
  @exec_main
  def __init__(self,**kwargs):
    super(SubentityUpdate,self).__init__(**kwargs)
    self.current_table_id=None
    self.current_values=None

  @abstractmethod
  def get_key(self): raise NotImplementedError

  @abstractproperty
  def values_class(self):raise NotImplementedError

  @abstractproperty
  def subentity_name(self):raise NotImplementedError

  def get_values_class(self):
    return self.values_class

  def get_value_class_kwargs(self):
    return {'subentity_name':self.subentity_name}

  @exec_main
  def update_values(self):
    try:
      key = self.get_key()
    except (gdb.error,RuntimeError):
      self.send_pkg_message_in_table('not available')
      self.current_table_id=None
      self.current_values=None
      return
    id,values = self.id_get(key)
    pkgs=[]
    if id!=None:
      #множество переменных, которые соотв. данному блоку было отрисовано ранее.
      #сравниваем значения отрис. ранее и значение перем. сейчас. Разницу отправляем
      #в граф. окно для перерисовки части таблицы
      if self.current_table_id!=id:
        #блок изменился
        pkgs.append(self.pkg_exemplar_set(id=id))
      need_update = values.need_update()
      if need_update:
        pkgs+=need_update
    else:
      #создаем таблицу для блока
      values_class = self.get_values_class()
      values = values_class(**self.get_value_class_kwargs())
      id = self.id_insert(key,values)
      try:
        table = values.get_table()
        pkgs.append(self.pkg_exemplar_create(table,id))
      except RuntimeError:
        self.key_drop(key)
    assert id!=None
    assert values!=None
    self.current_table_id=id
    self.current_values=values
    if pkgs:
      self.send_pkg_transaction(pkg)

  @exec_main
  def process_connection(self):
    self.update_values()


  def gdbevt_exited(self,pkg):
    self.clear_table()
  def gdbevt_stop(self,pkg):
    self.update_values()
  def gdbevt_new_objfile(self,pkg):
    self.update_values()
  def gdbevt_clear_objfiles(self,pkg):
    self.update_values()
  def gdbevt_memory_changed(self,pkg):
    self.update_values()
  def gdbevt_register_changed(self,pkg):
    self.update_values()

  def shellcmd_up(self,pkg):
    self.update_values()
  def shellcmd_down(self,pkg):
    self.update_values()
  def shellcmd_thread(self,pkg):
    self.update_values()

  def mcgdbevt_frame(self,pkg):
    self.update_values()

  def mcgdbevt_thread(self,pkg):
    self.update_values()

class OnclickVariables(TablePackages,CommunicationMixin):
  ''' Abstract class'''
  __metaclass__ = ABCMeta
  @abstractproperty
  def subentity_name(self): raise NotImplementedError

  @property
  def current_values(self): raise NotImplementedError

  @exec_main
  def onclick_expand_variable(self,pkg):
    if hasattr(self.current_values,'onclick_expand_variable'):
      need_update=self.current_values.onclick_expand_variable(pkg)
      if need_update:
        self.send(self.pkg_update_nodes(self.subentity_name,need_update))

  @exec_main
  def onclick_collapse_variable(self,pkg):
    if hasattr(self.current_values,'onclick_collapse_variable'):
      need_update=self.current_values.onclick_collapse_variable(pkg)
      if need_update:
        self.send(self.pkg_update_nodes(self.subentity_name,need_update))

  @exec_main
  def onclick_change_slice(self,pkg):
    if hasattr(self.current_values,'onclick_change_slice'):
      need_update=self.current_values.onclick_change_slice(pkg)
      if need_update:
        self.send(self.pkg_update_nodes(self.subentity_name,need_update))


  @exec_main
  def onclick_change_variable(self,pkg):
    try:
      if hasattr(self.current_values,'onclick_change_variable'):
        need_update = self.current_values.onclick_change_variable(pkg)
    except mcgdbChangevarErr as e:
      need_update=e.need_update
      self.send_error(str(e))
    if need_update:
      self.send(self.pkg_update_nodes(self.subentity_name,need_update))

class CurrentBacktrace(ValuesExemplar,TablePackages):
  def get_table(self):
    return self.one_row_one_cell(msg='Not available')
  def need_update(self):
    return []

class BacktraceTable(SubentityUpdate):
  subentity_name='backtrace'
  values_class=CurrentBacktrace

class BacktraceTable1(BaseSubentity,ValueToChunks):
  subentity_name='backtrace'

  def __init__(self,**kwargs):
    super(BacktraceTable1,self).__init__(**kwargs)

  def process_connection(self):
    return self.update_backtrace()

  @exec_main
  def _select_frame_1(self,nframe):
    if not gdb_stopped():
      self.send_error('inferior running')
      return
    if not inferior_alive ():
      self.send_error('inferior not alive')
      return
    n_cur_frame=0
    frame = gdb.newest_frame ()
    while frame:
      if n_cur_frame==nframe:
        frame.select()
        return
      n_cur_frame+=1
      frame = frame.older()
    self.send_error("can't find frame #{}".format(nframe))
    return

  def onclick_select_frame(self,pkg):
    nframe = pkg['nframe']
    self._select_frame_1(nframe)
    return [{'cmd':'mcgdbevt','mcgdbevt':'frame', 'data':{}}]


  @exec_main
  def get_stack(self):
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
          'cmd':'onclick',
          'onclick':'select_frame',
          'nframe' : nframe,
        }
      chunks = [
        framenumber,
        {'str':'  '},
      ] + self.get_frame_fileline(frame) + \
      [
        {'str':'\n'},
      ] + self.get_frame_funcname_with_args(frame)
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

  def update_backtrace(self):
    try:
      backtrace = self.get_stack()
    except gdb.error:
      return
    pkg={
      'cmd':'exemplar_create',
      'table_name':'backtrace',
      'table':backtrace,
      'id':1024,
      'set':True
    }
    self.send(pkg)



  def gdbevt_exited(self,pkg):
    self.clear_table()

  def gdbevt_stop(self,pkg):
    self.update_backtrace()

  def gdbevt_new_objfile(self,pkg):
    self.update_backtrace()

  def gdbevt_clear_objfiles(self,pkg):
    self.update_backtrace()

  def gdbevt_memory_changed(self,pkg):
    self.update_backtrace()

  def gdbevt_register_changed(self,pkg):
    self.update_backtrace()

  def shellcmd_up(self,pkg):
    self.update_backtrace()

  def shellcmd_down(self,pkg):
    self.update_backtrace()

  def shellcmd_thread(self,pkg):
    self.update_backtrace()

  def mcgdbevt_frame(self,pkg):
    self.update_backtrace()

  def mcgdbevt_thread(self,pkg):
    self.update_backtrace()


class ThreadRegs(ValuesExemplar,ValueToChunks):
  @exec_main
  def __init__(self,**kwargs):
    self.regvals={}
    self.regnames=[]
    self.regex_split = re.compile('\s*([^\s]+)\s+([^\s+]+)\s+(.*)')
    self.current_thread_num=None #Идентификатор потока. Регистры этого потока отрисованы в данный момент в удаленном окне
    regtab = gdb.execute('maint print registers',False,True).split('\n')[1:]
    for reg in regtab:
      if reg=="*1: Register type's name NULL.":
        continue
      reg=reg.split()
      if len(reg)>0 and reg[0] and reg[0]!="''" and len(reg[0])>0:
        regname='$'+reg[0]
        self.regnames.append(regname)
    super(ThreadRegs,self).__init__(**kwargs)


  @exec_main
  def get_table(self):
    if not gdb_stopped() or not inferior_alive ():
      raise RuntimeError
    rows_regs=[]
    for regname in self.regnames:
      regvalue = valcache(regname)
      self.regvals[regname] = str(regvalue)
      chunks=self.get_register_chunks(regname=regname, regvalue=regvalue)
      col  = {'chunks' : chunks}
      row  = {'columns' : [col]}
      rows_regs.append(row)
    return {'rows' : rows_regs}

  @exec_main
  def get_register_chunks(self,regname,regvalue):
    chunks=[]
    try:
      if regvalue.type.strip_typedefs().code==gdb.TYPE_CODE_INT:
        chunks += self.integer_as_struct_chunks(regvalue,regname)
      else:
        chunks += self.value_to_chunks(regvalue,regname, integer_mode='hex', disable_dereference=True, slice_clickable=False)
    except:
      gdb_print(regname+'\n')
      raise
    return chunks

  @exec_main
  def need_update(self):
    nodesdata=[]
    for regname in self.regnames:
      chunks=self.diff(self.Path(name=regname))
      nodesdata+=self.filter_chunks_with_id(chunks)
    return nodesdata


class RegistersTable(SubentityUpdate,OnclickVariables):
  subentity_name='registers'
  values_class = ThreadRegs

  @exec_main
  def get_key(self):
    thnum = get_this_thread_num() #current thread num
    if thnum==None:
      raise RuntimeError
    return 1024+thnum

class CurrentThreads(ValuesExemplar,TablePackages):
  def __init__(self,*args,**kwargs):
    super(CurrentThreads,self).__init__(*args,**kwargs)
    self.value_transform={
      'thread_name':lambda value : '"{}"\n'.format(value),
      'func_args':lambda value : frame_func_args(value),
    }

  def get_table(self):
    threads_info = self.get_threads_info()
    self.saved_threads_info = threads_info
    rows=[]
    gnums=threads_info.keys()
    gnums.sort()
    for global_num in gnums:
      thread_info=threads_info[global_num]
      row = self.new_threadrow(global_num,thread_info)
      rows.append(row)
    return {'rows':rows}

  def need_update(self):
    pkgs=[]
    threads_info = self.get_threads_info()
    exited_threads = set(self.saved_threads_info.keys()) - set(threads_info.keys())
    for global_num in exited_threads: #remove from GUI win exited threads
      rowid=self.id_threadrow(global_num)
      pkgs.append(self.pkg_drop_rows([rowid]))
    new_threads=[]
    for global_num in threads_info:
      thread_info = threads_info[global_num]
      if global_num not in self.saved_threads_info:
        #появился новый поток
        row=self.new_threadrow(global_num,thread_info)
        pkgs.append(self.pkg_append_rows([row]))
      else:
        saved_thread_info = self.saved_threads_info[global_num]
        pkgs += self.compare_infos(global_num,old=saved_thread_info,new=thread_info)
    self.saved_threads_info = threads_info
    return pkgs

  def compare_infos(self,global_num,new,old):
    upd=[]
    for target in ['thread_name','func_name','file_name','file_line','func_args']:
      if new[target]!=old[target]:
        upd.append(self.get_node(global_num,target,new[target]))
    return self.pkg_update_nodes(upd)

  def get_node(self,global_num,target,value):
    ''' Возвращает узел дерева типа target, с содержимым value'''
    getid=getattr(self,'id_{}'.format(target))
    if target in self.value_transform:
      value = self.value_transform[target](value)
    if type(value) is (str,unicode):
      return {'str':value,'id':getid(global_num)}
    else:
      return value

  def new_threadrow(self,global_num,thread_info):
    gn=global_num
    ti=thread_info
    tid=ti[gn]['tid']
    thread_name=ti[gn]['thread_name']
    func_name=ti[gn]['func_name']
    file_name=ti[gn]['file_name']
    func_args=ti[gn]['func_args']
    file_line=str(ti[gn]['file_line'])
    chunks=[
      {'str':'{global_num} LWP={tid} '.format(global_num=gn,tid=tid)},
      self.get_node(gn,'thread_name',thread_name),
      self.get_node(gn,'file_name',file_name),
      {'str':':'},
      self.get_node(gn,'file_line',file_line),
      self.get_node(gn,'func_name',func_name),
    ]
    if len(func_args)==0:
      chunks.append({'src':'()'})
    else:
      chunks.append({'src':'(\n'})
      chunks.append(self.get_node(gn,'func_args',func_args))
      chunks.append({'src':')'})
    col={'chunks':chunks}
    row={'columns':[col]}
    return row


  id_per_row = 6
  def id_threadrow(self,global_num):
    ''' Thread row id'''
    return self.id_per_row*global_num

  def id_thread_name(self,global_num):
    return self.id_per_row*global_num+1

  def id_func_name(self,global_num):
    return self.id_per_row*global_num+2

  def id_file_name(self,global_num):
    return self.id_per_row*global_num+3

  def id_file_line(self,global_num):
    return self.id_per_row*global_num+4

  def id_func_args(self,global_num):
    return self.id_per_row*global_num+5


  def get_threads_info(self):
    threads_info={}
    #сохраняем информацию о текущем треде и текущем фрейме, что бы потом восстановить
    selected_thread = gdb.selected_thread()
    selected_frame = gdb.selected_frame()
    for thread in gdb.selected_inferior().threads():
      thread.switch()
      frame = gdb.selected_frame()
      global_num    =   str(thread.global_num)
      tid           =   str(thread.ptid[1])
      threadname    =   str(thread.name) if thread.name else 'unknown'
      funcname = get_frame_funcname(frame)
      filename,fileline = get_frame_fileline(frame)
      funcargs = get_frame_func_args(frame)
      threads_info[global_num] = {
        'tid':tid,
        'thread_name':threadname,
        'func_name':funcname,
        'file_name':filename,
        'file_line':fileline,
        'func_args':funcargs,
      }
    if selected_thread != None:
      selected_thread.switch()
    if selected_frame != None:
      selected_frame.select()
    return threads_info




class ThreadsTable(SubentityUpdate):
  subentity_name='threads'
  values_class = CurrentThreads

  @exec_main
  def get_key(self):
    return 1024

  def onclick_select_thread(self,pkg):
    nthread = pkg['nthread']
    res=self.current_values.select_thread(nthread)
    if res!=None:
      self.send(res)
    return [{'cmd':'mcgdbevt','mcgdbevt':'thread', 'data':{}}]



class BlockLocalvarsTable(ValuesExemplar,ValueToChunks,TablePackages):
  ''' Локальные переменные для конкретного блока

      Для каждого встреченного блока создается объект типа BlockLocalvarsTable.
      Каждый блок характеризуется адресом начала, адресом конца и номером треда.

      В рамках LocalvarsTable хранятся экземпляры BlockLocalvarsTable.
      Если встречается ранее не встречавшийся блок, тогда создается новый экземпляр данного класса.
      Если встречается ранее встречавшийся блок, тогда в граф. окно отправляется команда, согласно которой
      текущей таблицей должна быть назначена таблица, соотв. текущему блоку. После этого вычисляется разница
      значений переменных для блока в предыдущий момент времени и в текущей момент. Вычисленная разница
      отправляется в граф. окно для обновления таблицы с лок. перменными.
  '''
  @exec_main
  def __init__(self,**kwargs):
    super(BlockLocalvarsTable,self).__init__(**kwargs)

  @exec_main
  def get_table(self):
    return self.get_local_vars()

  @exec_main
  def need_update(self):
    nodes = self.diff()
    if nodes:
      return self.pkg_update_nodes(nodes)
    else:
      return None

  @exec_main
  def get_local_vars(self):
    variables = self.get_local_vars_1 ()
    if len(variables)==0:
      return  {'rows':[]}
    lvars=[]
    funcname=self._get_frame_funcname(gdb.selected_frame())
    for name,value in variables.iteritems():
      chunks = self.value_to_chunks(value,name)
      check_chunks(chunks)
      col = {'chunks':chunks}
      row = {'columns':[col]}
      lvars.append(row)
    return {'rows':lvars}

  @exec_main
  def get_local_vars_1(self):
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
              variables[name] = valcache(symbol.value(frame))
      if block.function:
        break
      block = block.superblock
    return variables



class LocalvarsTable(SubentityUpdate,OnclickVariables):
  subentity_name='localvars'
  values_class = BlockLocalvarsTable

  @exec_main
  def get_key(self):
    blk=gdb.selected_frame().block()
    return (gdb.selected_thread().ptid[1],blk.start,blk.end)



class AuxWin(BaseWin):
  ''' Representation of window with localvars of current frame
  '''

  type='auxwin'
  startcmd='mcgdb open aux'
  subentities_cls=[RegistersTable, LocalvarsTable, BacktraceTable, ThreadsTable]





