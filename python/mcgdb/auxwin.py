#coding=utf8

import gdb

import re,sys,ctypes
import traceback


from mcgdb.basewin import BaseWin, StorageId, CommunicationMixin, TablePackages

from mcgdb.valuetochunks import check_chunks, ValueToChunks, get_frame_funcname, \
                                get_frame_fileline, get_frame_func_args, frame_func_args

from mcgdb.common  import exec_main, valcache, INDEX, INDEX_tmp, gdbprint, \
                    get_this_thread_num, mcgdbBaseException, mcgdbChangevarErr, \
                    gdb_stopped,inferior_alive,gdb_print, TABID_TMP, frame_func_addr



from abc import ABCMeta, abstractmethod, abstractproperty

class ValuesExemplar(object):
  __metaclass__ = ABCMeta

  def __init__(self,subentity_name,*args,**kwargs):
    self.__subentity_name = subentity_name
    super(ValuesExemplar,self).__init__(*args,**kwargs)

  @property
  def subentity_name(self):
    return self.__subentity_name

  @abstractmethod
  def get_table(self):
    ''' Return whole table for current inferior state'''
    raise NotImplementedError

  @abstractmethod
  def need_update(self):
    ''' This function compare saved inferior state with
        current inferior state and produce packages (with diff), that
        will be update GUI window

        Return value is list of packages.
    '''
    raise NotImplementedError


class BaseSubentity(TablePackages, CommunicationMixin):
  __metaclass__ = ABCMeta

  @exec_main
  def __init__(self,**kwargs):
    super(BaseSubentity,self).__init__(**kwargs)

  @abstractproperty
  def subentity_name(self):raise NotImplementedError

  def clear_table(self):
    self.send_pkg_message_in_table ('')



class SubentityUpdate(BaseSubentity,StorageId,TablePackages):
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

  @staticmethod
  def check_inferior_alive(f):
    def decorated(self,*args,**kwargs):
      if not inferior_alive():
        self.send_pkg_message_in_table('Inferior not alive')
        self.current_table_id=None
        self.current_values=None
        return
      return f(self,*args,**kwargs)
    return decorated

  def get_values_class(self):
    return self.values_class

  def get_value_class_kwargs(self):
    return {'subentity_name':self.subentity_name}

  @exec_main
  def update_values(self):
    if not inferior_alive():
      self.send_pkg_message_in_table('Inferior not alive')
      self.current_table_id=None
      self.current_values=None
      return
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
      self.send_pkg_transaction(pkgs)

  @exec_main
  def process_connection(self):
    self.update_values()


  def gdbevt_exited(self,pkg):
    self.send_pkg_message_in_table('inferior exited')
    self.current_table_id=None
    self.current_values=None

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

  @SubentityUpdate.check_inferior_alive
  def onclick_expand_variable(self,pkg):
    if hasattr(self.current_values,'onclick_expand_variable'):
      need_update=self.current_values.onclick_expand_variable(pkg)
      if need_update:
        self.send(self.pkg_update_nodes(need_update))

  @SubentityUpdate.check_inferior_alive
  def onclick_collapse_variable(self,pkg):
    if hasattr(self.current_values,'onclick_collapse_variable'):
      need_update=self.current_values.onclick_collapse_variable(pkg)
      if need_update:
        self.send(self.pkg_update_nodes(need_update))

  @SubentityUpdate.check_inferior_alive
  def onclick_change_slice(self,pkg):
    if hasattr(self.current_values,'onclick_change_slice'):
      need_update=self.current_values.onclick_change_slice(pkg)
      if need_update:
        self.send(self.pkg_update_nodes(need_update))


  @SubentityUpdate.check_inferior_alive
  def onclick_change_variable(self,pkg):
    try:
      if hasattr(self.current_values,'onclick_change_variable'):
        need_update = self.current_values.onclick_change_variable(pkg)
    except mcgdbChangevarErr as e:
      need_update=e.need_update
      self.send_error(str(e))
    if need_update:
      self.send(self.pkg_update_nodes(need_update))

class CurrentBacktrace(ValuesExemplar,TablePackages):
  def __init__(self,*args,**kwargs):
    super(CurrentBacktrace,self).__init__(*args,**kwargs)
    self.value_transform={
      'func_args'   : lambda th : frame_func_args(th['func_args']),
      'func_name'   : lambda th : {'str':th['func_name'], 'name':'frame_func_name'},
      'nframe'      : lambda th : {'str':'#{}'.format(th['nframe']),'selected':th['selected']},
    }
    self.selected_nframe=None

  def get_table(self):
    #return self.one_row_one_cell(msg='Not available')
    frames_info = self.get_frames_info()
    rows=[]
    for frame_info in frames_info:
      rows.append(self.new_framerow(frame_info))
    self.saved_frames_info = frames_info
    return {'rows':rows}

  def get_frames_info(self):
    frames_info=[]
    selected_frame = gdb.selected_frame()
    frame = gdb.newest_frame()
    nframe=0
    while frame:
      func_name = get_frame_funcname(frame)
      file_name,file_line = get_frame_fileline(frame)
      func_args = get_frame_func_args(frame)
      selected = (frame==selected_frame)
      if selected:
        self.selected_nframe = nframe
      frames_info.append({
        'nframe'    : nframe,
        'selected'  : selected,
        'func_name' : func_name,
        'file_name' : file_name,
        'file_line' : file_line,
        'func_args' : func_args,
      })
      frame = frame.older()
      nframe+=1
    return frames_info

  id_per_row = 3
  def id_nframe(self,nframe):
    return self.id_per_row*(nframe+1)+0

  def id_file_line(self,nframe):
    return self.id_per_row*(nframe+1)+1

  def id_func_args(self,nframe):
    return self.id_per_row*(nframe+1)+2

  def get_node(self,target,info):
    ''' Возвращает узел дерева типа target, с содержимым value'''
    getid=getattr(self,'id_{}'.format(target),None)
    if target in self.value_transform:
      value = self.value_transform[target](info)
    else:
      value = info[target]
    if type(value) in (dict,):
      #this is already node
      node = value
    else:
      node = {'str':unicode(value)}
    if getid:
      node['id'] = getid(info['nframe'])
    return node


  def new_framerow(self,frame_info):
    nframe=frame_info['nframe']
    chunks=[
      self.get_node('nframe',   frame_info),
      {'str':' '},
      self.get_node('file_name',frame_info),
      {'str':':'},
      self.get_node('file_line',frame_info),
      {'str':' '},
      self.get_node('func_name',frame_info),
      self.get_node('func_args',frame_info)
    ]
    onclick_data = {
      'cmd':'onclick',
      'onclick':'select_frame',
      'nframe' : nframe,
    }
    col={'chunks':chunks,'onclick_data':onclick_data}
    row={'columns':[col]}
    return row


  def need_update(self):
    frames_info = self.get_frames_info()
    assert len(frames_info)==len(self.saved_frames_info)
    nodesdata=[]
    for new,old in zip(frames_info,self.saved_frames_info):
      nodesdata+=self.compare_infos(new,old)
    self.saved_frames_info = frames_info
    return [self.pkg_update_nodes(nodesdata)]

  def compare_infos(self,new,old):
    upd=[]
    for target in ['file_line','func_args']:
      if new[target]!=old[target]:
        upd.append(self.get_node(target,new))
    if new['selected']!=old['selected']:
      upd.append(self.get_node('nframe',new))
    return upd


  def pkg_select_frame(self,nframe):
    return self.pkg_select_node(id=self.id_nframe(nframe),selected=True,visible=True)


  def pkg_unselect_frame(self,nframe):
    return self.pkg_select_node(id=self.id_nframe(nframe),selected=False)


  def select_frame(self,nframe):
    if self.selected_nframe == nframe:
      return
    frame = gdb.newest_frame()
    idx=0
    while frame:
      if idx==nframe:
        #found desired frame
        frame.select()
        pkgs=[]
        if self.selected_nframe!=None:
          pkgs.append(self.pkg_unselect_frame(self.selected_nframe))
        pkgs.append(self.pkg_select_frame(nframe))
        self.selected_nframe = nframe
        gdbprint(pkgs)
        if pkgs:
          return self.pkg_transaction(pkgs)
        else:
          return
      self.selected_nframe = nframe
      frame = frame.older()
      idx+=1
    self.send_error("can't find selected frame")
    #It seems that in gui window show old frame data, because user select unexisted thread.
    #Update this.
    return self.need_update()



class BacktraceTable(SubentityUpdate):
  subentity_name='backtrace'
  values_class=CurrentBacktrace

  def get_key(self):
    addrs=[]
    frame = gdb.newest_frame()
    while frame:
      _,start,stop = frame_func_addr (frame)
      addrs.append((start,stop))
      frame = frame.older()
    global_num = gdb.selected_thread().global_num
    return (global_num,tuple(addrs))

  @SubentityUpdate.check_inferior_alive
  def onclick_select_frame(self,pkg):
    if self.current_values:
      res=self.current_values.select_frame(int(pkg['nframe']))
      if res!=None:
        self.send(res)
        return [{'cmd':'mcgdbevt','mcgdbevt':'frame', 'data':{}}]



class ThreadRegs(ValuesExemplar,ValueToChunks, TablePackages):
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
    if nodesdata:
      return [self.pkg_update_nodes(nodesdata)]


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
      'thread_name' :lambda th : '"{}"\n'.format(th['thread_name']),
      'func_args'   :lambda th : frame_func_args(th['func_args']),
      'func_name'   :lambda th : {'str':th['func_name'], 'name':'frame_func_name'},
      'global_num'  :lambda th : {'str':str(th['global_num']),'selected':th['selected']},
    }

  @exec_main
  def get_table(self):
    threads_info = self.get_threads_info()
    self.saved_threads_info = threads_info
    self.selected_global_num = gdb.selected_thread().global_num
    rows=[]
    gnums=threads_info.keys()
    gnums.sort()
    for global_num in gnums:
      thread_info=threads_info[global_num]
      row = self.new_threadrow(thread_info)
      rows.append(row)
    return {'rows':rows}

  @exec_main
  def need_update(self):
    pkgs=[]
    threads_info = self.get_threads_info()
    exited_threads = set(self.saved_threads_info.keys()) - set(threads_info.keys())
    rm_rowids=[]
    for global_num in exited_threads: #remove from GUI win exited threads
      rm_rowids.append(self.id_threadrow(global_num))
    if rm_rowids:
      pkgs.append(self.pkg_drop_rows(rm_rowids))
    new_threads=[]
    append_rows=[]
    for global_num in threads_info:
      thread_info = threads_info[global_num]
      if global_num not in self.saved_threads_info:
        #появился новый поток
        row = self.new_threadrow(thread_info)
        append_rows.append(row) #добавляем для него строку
      else:
        saved_thread_info = self.saved_threads_info[global_num]
        pkgs.append(self.compare_infos(global_num,old=saved_thread_info,new=thread_info))
    if append_rows:
      pkgs.append(self.pkg_append_rows(append_rows))
    self.saved_threads_info = threads_info
    self.selected_global_num = gdb.selected_thread().global_num
    return pkgs

  def compare_infos(self,global_num,new,old):
    upd=[]
    for target in ['thread_name','func_name','file_name','file_line','func_args']:
      if new[target]!=old[target]:
        upd.append(self.get_node(global_num,target,new))
    if new['selected']!=old['selected']:
      upd.append(self.get_node(global_num,'global_num',new))
    if upd:
      return self.pkg_update_nodes(upd)

  def get_node(self,global_num,target,thread_info):
    ''' Возвращает узел дерева типа target, с содержимым value'''
    getid=getattr(self,'id_{}'.format(target))
    if target in self.value_transform:
      value = self.value_transform[target](thread_info)
    else:
      value = thread_info[target]
    if type(value) in (dict,):
      #this is already node
      node = value
    else:
      node = {'str':unicode(value)}
    node['id'] = getid(global_num)
    return node

  def new_threadrow(self,thread_info):
    gn=thread_info['global_num']
    chunks=[
      self.get_node(gn,'global_num',thread_info),
      {'str':' LWP={tid} '.format(tid=thread_info['tid'])},
      self.get_node(gn,'thread_name',thread_info),
      self.get_node(gn,'file_name',thread_info),
      {'str':':'},
      self.get_node(gn,'file_line',thread_info),
      {'str':' '},
      self.get_node(gn,'func_name',thread_info),
      self.get_node(gn,'func_args',thread_info)
    ]
    onclick_data={
      'cmd' : 'onclick',
      'onclick':'select_thread',
      'global_num':gn,
    }
    col={'chunks':chunks,'onclick_data':onclick_data}
    row={'columns':[col],'id':self.id_threadrow(gn)}
    return row

  def pkg_select_thread(self,global_num):
    return self.pkg_select_node(id=self.id_global_num(global_num),selected=True,visible=True)

  def pkg_unselect_thread(self,global_num):
    return self.pkg_select_node(id=self.id_global_num(global_num),selected=False)


  def select_thread(self,global_num):
    if self.selected_global_num == global_num:
      return
    for thread in gdb.selected_inferior().threads():
      if thread.global_num==global_num:
        thread.switch()
        pkgs=[
          self.pkg_unselect_thread(self.selected_global_num),
          self.pkg_select_thread(global_num),
        ]
        self.selected_global_num = global_num
        return self.pkg_transaction(pkgs)
    self.send_error("can't find selected thread")
    #It seems that in gui window show old thread data, because user select unexisted thread.
    #Update this.
    return self.need_update()

  id_per_row = 7
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

  def id_global_num(self,global_num):
    return self.id_per_row*global_num+6



  def get_threads_info(self):
    threads_info={}
    #сохраняем информацию о текущем треде и текущем фрейме, что бы потом восстановить
    selected_thread = gdb.selected_thread()
    selected_frame = gdb.selected_frame()
    for thread in gdb.selected_inferior().threads():
      thread.switch()
      frame = gdb.selected_frame()
      global_num    =   thread.global_num
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
        'selected' :selected_thread.global_num==global_num,
        'global_num':global_num,
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

  @exec_main
  def onclick_select_thread(self,pkg):
    if self.current_values and inferior_alive():
      res=self.current_values.select_thread(int(pkg['global_num']))
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
      return [self.pkg_update_nodes(nodes)]
    else:
      return None

  @exec_main
  def get_local_vars(self):
    variables = self.get_local_vars_1 ()
    if len(variables)==0:
      return  {'rows':[]}
    lvars=[]
    funcname=get_frame_funcname(gdb.selected_frame())
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





