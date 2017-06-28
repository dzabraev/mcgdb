#coding=utf8

import gdb

import re,sys,ctypes
import traceback


from mcgdb.basewin import BaseWin,TABID_TMP
from mcgdb.common  import gdb_stopped,inferior_alive,gdb_print, TablePackages
from mcgdb.valuetochunks import check_chunks, ValueToChunks
from mcgdb.common  import exec_main, valcache, INDEX, INDEX_tmp, \
                    get_this_thread_num


class BaseSubentity(ValueToChunks, TablePackages):
  @exec_main
  def __init__(self,INDEX=None,**kwargs):
    self.send = kwargs['send']
    self.send_error = kwargs['send_error']
    super(BaseSubentity,self).__init__(INDEX,**kwargs)

  def set_message_in_table(self,msg,id=TABID_TMP,set_current=True):
    pkg={
      'cmd':'exemplar_create',
      'table':{'rows':[{'columns':[{'chunks':[{'str':msg}]}]}]},
      'table_name':self.subentity_name,
      'id':id,
    }
    if set_current:
      pkg['set'] = set_current
    self.send(pkg)

  def clear_table(self):
    self.set_message_in_table ('')


class BacktraceTable(BaseSubentity):
  subentity_name='backtrace'

  def __init__(self,**kwargs):
    super(BacktraceTable,self).__init__(**kwargs)

  def process_connection(self):
    return self.update_backtrace()

  @exec_main
  def _select_frame_1(self,nframe):
    if not gdb_stopped():
      return 'inferior running'
    if not inferior_alive ():
      return 'inferior not alive'
    n_cur_frame=0
    frame = gdb.newest_frame ()
    while frame:
      if n_cur_frame==nframe:
        frame.select()
        return
      n_cur_frame+=1
      frame = frame.older()
    return "can't find frame #{}".format(nframe)

  def onclick_select_frame(self,pkg):
    nframe = pkg['nframe']
    res=self._select_frame_1(nframe)
    if res!=None:
      self.send_error(res)
    else:
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
      ] + self._get_frame_fileline(frame) + \
      [
        {'str':'\n'},
      ] + self._get_frame_funcname_with_args(frame)
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




class RegistersTable(BaseSubentity):
  subentity_name='registers'

  @exec_main
  def __init__(self, **kwargs):
    self.regnames=[]
    self.regex_split = re.compile('\s*([^\s]+)\s+([^\s+]+)\s+(.*)')
    self.registers_drawn=[] #Список идентификаторов потоков, для которых была произведена первичная отрисовка регистров
    self.current_thread_num=None #Идентификатор потока. Регистры этого потока отрисованы в данный момент в удаленном окне
    regtab = gdb.execute('maint print registers',False,True).split('\n')[1:]
    for reg in regtab:
      if reg=="*1: Register type's name NULL.":
        continue
      reg=reg.split()
      if len(reg)>0 and reg[0] and reg[0]!="''" and len(reg[0])>0:
        regname='$'+reg[0]
        self.regnames.append(regname)
    super(RegistersTable,self).__init__(INDEX,thread_depend=False,frame_depend=False, **kwargs)

  def process_connection(self):
    return self.update_registers_initial()

  @exec_main
  def update_registers_initial(self):
    thnum = get_this_thread_num()
    if thnum==None:
      return
    try:
      regs = self.get_registers()
      if regs!=None:
        self.registers_drawn.append(thnum)
      else:
        regs={'rows':[]}
    except gdb.error as e:
      if e.message=="No registers.":
        return
      else:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        raise exc_type, exc_value, exc_traceback
    pkg={
      'cmd':'exemplar_create',
      'table_name':'registers',
      'table':regs,
      'id':1024+thnum,
      'set':True,
    }
    self.send(pkg)
    tabdata={}
    for regname in self.regnames:
      try:
        regval = valcache(regname)
      except gdb.error:
        regval = None
      tabdata[regname]=regval
    INDEX((self.subentity_name,thnum),tabdata)
    self.current_thread_num = thnum

  @exec_main
  def get_registers(self):
    if not gdb_stopped() or not inferior_alive ():
      return
    return self._get_registers()

  @exec_main
  def get_register_chunks(self,regname):
    regvalue = valcache(regname)
    chunks=[]
    try:
      if regvalue.type.strip_typedefs().code==gdb.TYPE_CODE_INT:
        chunks += self.integer_as_struct_chunks(regvalue,regname)
      else:
        chunks += self.value_to_chunks(regvalue,regname, integer_mode='hex', disable_dereference=True, max_deref_depth=None,slice_clickable=False)
    except:
      gdb_print(regname+'\n')
      raise
    return chunks

  def _get_registers(self):
    rows_regs=[]
    for regname in self.regnames:
      chunks=self.get_register_chunks(regname)
      col  = {'chunks' : chunks}
      row  = {'columns' : [col]}
      rows_regs.append(row)
    return {'rows' : rows_regs}

  def update_regnodes (self,nodes_data):
    return {'cmd':'update_nodes', 'table_name':'registers', 'nodes':nodes_data}

  def update_register_data(self,regname):
    chunks = self.get_register_chunks(regname)
    chunks_with_id = self.filter_chunks_with_id(chunks)
    nodes_data=[]
    for chunk in chunks_with_id:
      assert 'id' in chunk
      #nodes_data.append(self.update_regnode_data (chunk))
      nodes_data.append(chunk)
    return nodes_data


  @exec_main
  def update_registers(self):
    if not gdb_stopped():
      return
    thnum = get_this_thread_num()
    if not thnum in self.registers_drawn:
      self.update_registers_initial()
      return
    if thnum!=self.current_thread_num:
      #поток был изменен. Необходимо изменить экземпляр таблицы регистров
      #в граф. окне.
      self.exemplar_set(1024+thnum,'registers')
      self.current_thread_num = thnum
    nodesdata=[]
    tabidx,tabdata=INDEX.get((self.subentity_name,thnum))
    for regname in self.regnames:
      regvalue = valcache(regname)
      #register value cast to string because by default
      #gdb.Value will be cast into long or int and python will
      #raise exception:
      #Python Exception <class 'gdb.error'> That operation is not available on integers of more than 8 bytes.:
      if str(tabdata[regname])!=str(regvalue):
        nodesdata+=self.update_register_data(regname)
        tabdata[regname]=regvalue
    if nodesdata:
      self.send(self.update_regnodes(nodesdata))

  #GDB EVENTS
  def gdbevt_exited(self,pkg):
    self.clear_table()
    self.registers_drawn=False

  def gdbevt_stop(self,pkg):
    return self.update_registers()

  def gdbevt_register_changed(self,pkg):
    return self.update_registers()

  #SHELL COMMANDS
  def shellcmd_up(self,pkg):
    return self.update_registers()

  def shellcmd_down(self,pkg):
    return self.update_registers()

  def shellcmd_thread(self,pkg):
    return self.update_registers()

  #MCGDB EVENTS
  def mcgdbevt_frame(self,pkg):
    return self.update_registers()

  def mcgdbevt_thread(self,pkg):
    return self.update_registers()

  def onclick_expand_variable(self,pkg):
    super(RegistersTable,self).onclick_expand_variable(pkg)
    self.update_registers()

  def onclick_collapse_variable(self,pkg):
    super(RegistersTable,self).onclick_collapse_variable(pkg)
    self.update_registers()

  def onclick_change_slice(self,pkg):
    super(RegistersTable,self).onclick_change_slice(pkg)
    self.update_registers()

  def onclick_change_variable(self,pkg):
    super(RegistersTable,self).onclick_change_variable(pkg)
    self.update_registers()




class ThreadsTable(BaseSubentity):
  subentity_name='threads'

  @exec_main
  def __init__(self, **kwargs):
    super(ThreadsTable,self).__init__(**kwargs)

  def process_connection(self):
    return self.update_threads()

  @exec_main
  def _select_thread_1(self,nthread):
    threads=gdb.selected_inferior().threads()
    if len(threads)<nthread+1:
      return 'thread #{} not exists'.format(nthread)
    threads[nthread].switch()

  def onclick_select_thread(self,pkg):
    nthread = pkg['nthread']
    res=self._select_thread_1(nthread)
    if res!=None:
      self.send_error(res)
    else:
      # об этом остальные сущности о смене потока
      return [{'cmd':'mcgdbevt','mcgdbevt':'thread', 'data':{}}]

  def update_threads(self):
    try:
      self.send({
        'cmd':'exemplar_create',
        'table_name':'threads',
        'table':self.get_threads(),
        'id':1024,
        'set':True,
      })
    except:
      return


  @exec_main
  def get_threads(self):
    selected_thread = gdb.selected_thread()
    selected_frame = gdb.selected_frame()
    throws=[]
    threads=gdb.selected_inferior().threads()
    nrow=0
    selected_row=None
    for thread in threads:
      column={}
      thread.switch()
      frame = gdb.selected_frame()
      global_num    =   str(thread.global_num)
      tid           =   str(thread.ptid[1])
      threadname    =   str(thread.name) if thread.name else ''
      funcname      =   self._get_frame_funcname_with_args(frame)
      fileline      =   self._get_frame_fileline(frame)
      global_num_chunk = {'str':global_num, 'name':'th_global_num'}
      if thread==selected_thread:
        global_num_chunk['selected']=True
        selected_row=nrow
      column['onclick_data'] = {
          'cmd' : 'onclick',
          'onclick':'select_thread',
          'nthread' : nrow,
        }
      chunks = [ global_num_chunk,
          {'str':'  '},
          {'str':tid,        'name':'th_tid'},
          {'str':'  '},
          {'str':'"'},
          {'str':threadname,     'name':'th_threadname'},
          {'str':'"\n'},
        ] +  \
        fileline + \
        [{'str':'\n'}] + \
        self._get_frame_funcname_with_args(frame)
      column['chunks'] = chunks
      row={'columns' : [column]}
      throws.append(row)
      nrow+=1
    if selected_thread != None:
      selected_thread.switch()
    if selected_frame != None:
      selected_frame.select()
    table = {
      'rows':throws,
    }
    if selected_row!=None:
      table['selected_row'] = selected_row
    return table

  #GDB EVENTS
  def gdbevt_exited(self,evt):
    self.clear_table()

  def gdbevt_stop(self,evt):
    self.update_threads()

  def gdbevt_new_objfile(self,evt):
    self.update_threads()

  def gdbevt_clear_objfiles(self,evt):
    self.update_threads()

  def gdbevt_memory_changed(self,evt):
    self.update_threads()

  def gdbevt_register_changed(self,evt):
    self.update_threads()

  #SHELL COMMANDS
  def shellcmd_up(self,data=None):
    self.update_threads()

  def shellcmd_down(self,data=None):
    self.update_threads()

  def shellcmd_thread(self,data=None):
    self.update_threads()

  #MCGDB EVENTS
  def mcgdbevt_frame(self,data):
    self.update_threads()

  def mcgdbevt_thread(self,data):
    self.update_threads()




class LocalvarsTable(BaseSubentity):
  subentity_name='localvars'

  @exec_main
  def __init__(self,**kwargs):
    super(LocalvarsTable,self).__init__(INDEX_tmp,**kwargs)

  def process_connection(self):
    self.update_localvars()

  def get_lvars_diff(self,data):
    need_update=[]
    new_data=[]
    for path,value in data:
      new_value = valcache(path)
      new_data.append(path,new_value)
      if unicode(value) != unicode(new_value):
        chunks = self.filter_chunks_with_id(self.value_to_chunks(new_value))
        need_update.append(chunks)
    return tuple(new_data),need_update

  def update_localvars(self):
    block_key = self.get_this_block_key()
    id,data = self.id_get(block_key)
    if id!=None:
      #множество переменных, которые соотв. данному блоку было отрисовано ранее.
      #сравниваем значения отрис. ранее и значение перем. сейчас. Разницу отправляем
      #в граф. окно для перерисовки части таблицы
      new_data,need_update=self.get_lvars_diff(data)
      self.id_update(block_key,new_data)
      pkg={'cmd':'update_nodes', 'table_name':'localvars', 'nodes':need_update}
    else:
      printed_variables,lvars=self._get_local_vars()
      id = self.id_insert(block_key,printed_variables)
      pkg={ 'cmd':'exemplar_create',
            'table_name':'localvars',
            'table':lvars,
            'id':id,
            'set':True,
          }
    self.send(pkg)

  @exec_main
  def get_this_block_key(self):
    variables = []
    funcname=self._get_frame_funcname(gdb.selected_frame())
    while block:
      for symbol in block:
        if (symbol.is_argument or symbol.is_variable):
            name = symbol.name
            if name not in variables:
              variable=valcache(symbol.value(frame))
              variables.append( (name,variable.type.strip_typedefs().code) )
      if block.function:
        break
      block = block.superblock
    key=(funcname,tuple(variables))
    return key


  @exec_main
  def _get_local_vars(self):
    variables = self._get_local_vars_1 ()
    if len(variables)==0:
      return  {'rows':[]}
    lvars=[]
    funcname=self._get_frame_funcname(gdb.selected_frame())
    printed_variables=[]
    for name,value in variables.iteritems():
      chunks = self.value_to_chunks(value,name,funcname=funcname,printed_variables=printed_variables)
      check_chunks(chunks)
      col = {'chunks':chunks}
      row = {'columns':[col]}
      lvars.append(row)
    return printed_variables,{'rows':lvars}

  def _get_local_vars_1(self):
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

  def docheckpkg(self,pkg):
    return self.INDEX.get_by_idx(pkg['parent_id'])

  @exec_main
  def onclick_expand_variable(self,pkg):
    #gdb_print(gdb.selected_frame().name()+'\n')
    if gdb.selected_frame().name()=='sem_wait':
      traceback.print_stack()
    self.docheckpkg(pkg)
    super(LocalvarsTable,self).onclick_expand_variable(pkg)
    self.update_localvars()

  @exec_main
  def onclick_collapse_variable(self,pkg):
    self.docheckpkg(pkg)
    super(LocalvarsTable,self).onclick_collapse_variable(pkg)
    self.update_localvars()

  @exec_main
  def onclick_change_slice(self,pkg):
    self.docheckpkg(pkg)
    super(LocalvarsTable,self).onclick_change_slice(pkg)
    self.update_localvars()

  @exec_main
  def onclick_change_variable(self,pkg):
    self.docheckpkg(pkg)
    super(LocalvarsTable,self).onclick_change_variable(pkg)
    self.update_localvars()

  def gdbevt_exited(self,pkg):
    self.clear_table()
  def gdbevt_stop(self,pkg):
    self.update_localvars()
  def gdbevt_new_objfile(self,pkg):
    self.update_localvars()
  def gdbevt_clear_objfiles(self,pkg):
    self.update_localvars()
  def gdbevt_memory_changed(self,pkg):
    self.update_localvars()
  def gdbevt_register_changed(self,pkg):
    self.update_localvars()

  def shellcmd_up(self,pkg):
    self.update_localvars()
  def shellcmd_down(self,pkg):
    self.update_localvars()
  def shellcmd_thread(self,pkg):
    self.update_localvars()

  def mcgdbevt_frame(self,pkg):
    self.update_localvars()

  def mcgdbevt_thread(self,pkg):
    self.update_localvars()




class AuxWin(BaseWin):
  ''' Representation of window with localvars of current frame
  '''

  type='auxwin'
  startcmd='mcgdb open aux'

  @exec_main
  def __init__(self, **kwargs):
    kwtab={
      'send'        :   self.send,
      'send_error'  :   self.send_error,
    }
    self.subentities={
      'registers' : RegistersTable(**kwtab),
      'localvars' : LocalvarsTable(**kwtab),
      'backtrace' : BacktraceTable(**kwtab),
      'threads'   : ThreadsTable(**kwtab),
    }
    super(AuxWin,self).__init__(**kwargs)

  def process_connection(self):
    return super(AuxWin,self).process_connection()




