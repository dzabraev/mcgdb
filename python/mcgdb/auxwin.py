#coding=utf8

import gdb

import re,sys,ctypes

from mcgdb.basewin import BaseWin
from mcgdb.common  import exec_in_main_pythread,gdb_stopped,inferior_alive,gdb_print
from mcgdb.basewin import stringify_value,valueaddress_to_ulong,stringify_value_safe, \
                          is_incomplete_type_ptr,check_chunks
from mcgdb.common import exec_main


class FrameCommon(ValueToChunks):
  def _get_frame_func_args(self,frame):
      args=[]
      try:
        block=frame.block()
      except RuntimeError:
        return []
      while block:
        for sym in block:
          if sym.is_argument:
            value = self.valcache(sym.value(frame))
            args.append(
              (sym.name,stringify_value(value))
            )
        if block.function:
          break
        block=block.superblock
        if (not block):
          break
      return args

  def _get_frame_funcname(self,frame):
    frame_func_name = frame.name()
    return frame_func_name

  def _get_frame_funcname_with_args(self,frame):
    frame_func_name = {'str':self._get_frame_funcname(frame),'name':'frame_func_name'}
    frame_func_args = []
    func_args = self._get_frame_func_args(frame)
    for argname,argval in func_args:
      frame_func_args.append({'str':'\n  '})
      frame_func_args.append({'str':argname,'name':'varname'})
      frame_func_args.append({'str':'='})
      frame_func_args.append({'str':argval, 'name':'varvalue'})
    res = [frame_func_name, {'str':'('}] + frame_func_args
    if len(func_args) > 0:
      res.append ({'str':'\n)'})
    else :
      res.append ({'str':')'})
    return res


  def _get_frame_fileline(self,frame):
    frame_line      = frame.find_sal().line
    symtab = frame.find_sal().symtab
    frame_filename  = symtab.filename if symtab else 'unknown'
    return [
      {'str':frame_filename,'name':'frame_filename'},
      {'str':':', 'name':'frame_fileline_delimiter'},
      {'str':str(frame_line),'name':'frame_line'},
    ]

  def filter_chunks_with_id(self,chunks):
    ok=[]
    for chunk in chunks:
      if 'id' in chunk:
        ok.append(chunk)
      if 'chunks' in chunk:
        ok+=self.filter_chunks_with_id(chunk['chunks'])
    return ok



class BacktraceTable(FrameCommon):
  def __init__(self,**kwargs):
    self.register_onclick_action('select_frame',self._select_frame)
    super(BacktraceTable,self).__init__(**kwargs)

  def process_connection(self):
    rc=super(BacktraceTable,self).process_connection()
    self.update_backtrace()
    return rc

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

  def _select_frame(self,pkg):
    nframe = pkg['data']['nframe']
    res=self._select_frame_1(nframe)
    if res!=None:
      self.send_error(res)
    else:
      return [{'cmd':'mcgdbevt','cmdname':'frame', 'data':{}}]


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
          'click_cmd':'select_frame',
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
      'cmd':'backtrace',
      'table':backtrace,
    }
    self.send(pkg)



  def gdbevt_exited(self,evt):
    self.update_backtrace()
    super(BacktraceTable,self).gdbevt_exited(evt)

  def gdbevt_stop(self,evt):
    self.update_backtrace()
    super(BacktraceTable,self).gdbevt_stop(evt)

  def gdbevt_new_objfile(self,evt):
    self.update_backtrace()
    super(BacktraceTable,self).gdbevt_new_objfile(evt)

  def gdbevt_clear_objfiles(self,evt):
    self.update_backtrace()
    super(BacktraceTable,self).gdbevt_clear_objfiles(evt)

  def gdbevt_memory_changed(self,evt):
    self.update_backtrace()
    super(BacktraceTable,self).gdbevt_memory_changed(evt)

  def gdbevt_register_changed(self,evt):
    self.update_backtrace()
    super(BacktraceTable,self).gdbevt_register_changed(evt)

  def shellcmd_frame_up(self):
    self.update_backtrace()
    super(BacktraceTable,self).shellcmd_frame_up()

  def shellcmd_frame_down(self):
    self.update_backtrace()
    super(BacktraceTable,self).shellcmd_frame_down()

  def shellcmd_thread(self):
    self.update_backtrace()
    super(BacktraceTable,self).shellcmd_thread()

  def mcgdbevt_frame(self,data):
    self.update_backtrace()
    super(BacktraceTable,self).mcgdbevt_frame(data)

  def mcgdbevt_thread(self,data):
    self.update_backtrace()
    super(BacktraceTable,self).mcgdbevt_frame(data)




class RegistersTable(ValueToChunks):
  __tabname='registers'
  def __init__(self, **kwargs):
    self.regnames=[]
    self.converters['bin_to_long'] = lambda x: long(x,2)
    self.converters['hex_to_long'] = lambda x: long(x,16)
    self.regex_split = re.compile('\s*([^\s]+)\s+([^\s+]+)\s+(.*)')
    self.registers_drawn=False
    regtab = gdb.execute('maint print registers',False,True).split('\n')[1:]
    for reg in regtab:
      if reg=="*1: Register type's name NULL.":
        continue
      reg=reg.split()
      if len(reg)>0 and reg[0] and reg[0]!="''" and len(reg[0])>0:
        regname='$'+reg[0]
        self.regnames.append(regname)
    super(RegistersTable,self).__init__(**kwargs)


  def process_connection(self):
    rc=super(RegistersTable,self).process_connection()
    self.update_registers_initial()
    return rc

  @exec_main
  def update_registers_initial(self):
    try:
      regs = self.get_registers()
      if regs!=None:
        self.registers_drawn=True
    except gdb.error as e:
      if e.message=="No registers.":
        return
      else:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        raise exc_type, exc_value, exc_traceback
    pkg={
      'cmd':'registers',
      'table':regs,
    }
    self.send(pkg)
    tabdata={}
    for regname in self.regnames:
      try:
        regval = self.valcache(regname)
      except gdb.error:
        regval = None
      tabdata[regname]=regval
    self.insert_table_exemplar(self.__tabname,None,tabdata)

  @exec_main
  def get_registers(self):
    if not gdb_stopped() or not inferior_alive ():
      return
    return self._get_registers()

  def get_register_chunks(self,regname):
    regvalue = self.valcache(regname)
    chunks=[]
    try:
      if regvalue.type.strip_typedefs().code==gdb.TYPE_CODE_INT:
        chunks += self.integer_as_struct_chunks(regvalue,regname)
      else:
        chunks += self.value_to_chunks(regvalue,regname, integer_mode='hex', disable_dereference=True, max_deref_depth=None)
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

  def update_regnode_pkg (self,node_data):
    return {'cmd':'update_node','table':'registers', 'node_data':node_data}

  '''
  def pkgs_update_register(self,regname,value):
    pkgs=[]
    if value.type.strip_typedefs().code==gdb.TYPE_CODE_INT:
      chunks=[
        self.changable_value_to_chunks(value,regname,integer_mode='dec',index_name=regname+'_dec')[0],
        self.changable_value_to_chunks(value,regname,integer_mode='hex',index_name=regname+'_hex',converter='hex_to_long')[0],
        self.changable_value_to_chunks(value,regname,integer_mode='bin',index_name=regname+'_bin',converter='bin_to_long')[0],
      ]
    else:
      chunks = [self.changable_value_to_chunks(value,regname,integer_mode='hex',converter='hex_to_long')[0]]
    for d in :
      pkgs.append(self.update_regnode_pkg ({
        'id':d['id']),
        'str':d['str'],
        'onclick_data':d['onclick_data'],
      }))
    return pkgs
  '''
  def pkgs_update_register(self,regname):
    chunks = self.get_register_chunks(regname)
    chunks_with_id = self.filter_chunks_with_id(chunks)
    pkgs=[]
    for chunk in chunks_with_id:
      assert 'id' in chunk
      pkgs.append(self.update_regnode_pkg (chunk))
    return pkgs


  @exec_main
  def update_registers(self):
    if not self.registers_drawn:
      self.update_registers_initial()
      return
    packages=[]
    tabidx,tabdata=self.get_table_exemplar(self.__tabname,None)
    for regname in self.regnames:
      regvalue = self.valcache(regname)
      if tabdata[regname]!=regvalue:
        packages+=self.pkgs_update_register(regname)
        tabdata[regname]=regvalue
    self.send(packages)

  def gdbevt_exited(self,evt):
    self.update_registers()
    return super(RegistersTable,self).gdbevt_exited(evt)

  def gdbevt_stop(self,evt):
    self.update_registers()
    return super(RegistersTable,self).gdbevt_stop(evt)

  def gdbevt_register_changed(self,evt):
    self.update_registers()
    return super(RegistersTable,self).gdbevt_register_changed(evt)

  def shellcmd_frame_up(self):
    self.update_registers()
    return super(RegistersTable,self).shellcmd_frame_up()

  def shellcmd_frame_down(self):
    self.update_registers()
    return super(RegistersTable,self).shellcmd_frame_down()

  def shellcmd_thread(self):
    self.update_registers()
    return super(RegistersTable,self).shellcmd_thread()

  def mcgdbevt_frame(self,data):
    self.update_registers()
    super(RegistersTable,self).mcgdbevt_frame(data)

  def mcgdbevt_thread(self,data):
    self.update_registers()
    super(RegistersTable,self).mcgdbevt_frame(data)



class ThreadsTable(FrameCommon):
  def __init__(self, **kwargs):
    self.click_cmd_cbs['select_thread'] = self._select_thread
    super(ThreadsTable,self).__init__(**kwargs)

  def process_connection(self):
    rc=super(ThreadsTable,self).process_connection()
    self.update_threads()
    return rc

  @exec_main
  def _select_thread_1(self,nthread):
    threads=gdb.selected_inferior().threads()
    if len(threads)<nthread+1:
      return 'thread #{} not exists'.format(nthread)
    threads[nthread].switch()

  def _select_thread(self,pkg):
    nthread = pkg['data']['nthread']
    res=self._select_thread_1(nthread)
    if res!=None:
      self.send_error(res)
    else:
      # имитируем, что пользователь вызвал в шелле команду, и оповещаем
      # об этом остальные сущности
      return [{'cmd':'mcgdbevt','cmdname':'thread', 'data':{}}]

  def update_threads(self):
    try:
      self.send({
        'cmd':'threads',
        'table':self.get_threads(),
      })
    except:
      return


  @exec_main
  def get_threads(self):
    selected_thread = gdb.selected_thread()
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
          'click_cmd':'select_thread',
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
    if selected_thread!=None:
      selected_thread.switch()
    table = {
      'rows':throws,
    }
    if selected_row!=None:
      table['selected_row'] = selected_row
    return table

  def gdbevt_exited(self,evt):
    self.update_threads()
    super(ThreadsTable,self).gdbevt_exited(evt)
  def gdbevt_stop(self,evt):
    self.update_threads()
    super(ThreadsTable,self).gdbevt_stop(evt)
  def gdbevt_new_objfile(self,evt):
    self.update_threads()
    super(ThreadsTable,self).gdbevt_new_objfile(evt)
  def gdbevt_clear_objfiles(self,evt):
    self.update_threads()
    super(ThreadsTable,self).gdbevt_clear_objfiles(evt)
  def gdbevt_memory_changed(self,evt):
    self.update_threads()
    super(ThreadsTable,self).gdbevt_memory_changed(evt)
  def gdbevt_register_changed(self,evt):
    self.update_threads()
    super(ThreadsTable,self).gdbevt_register_changed(evt)

  def shellcmd_frame_up(self):
    self.update_threads()
    super(ThreadsTable,self).shellcmd_frame_up()
  def shellcmd_frame_down(self):
    self.update_threads()
    super(ThreadsTable,self).shellcmd_frame_down()
  def shellcmd_thread(self):
    self.update_threads()
    super(ThreadsTable,self).shellcmd_thread()

  def mcgdbevt_frame(self,data):
    self.update_threads()
    super(ThreadsTable,self).mcgdbevt_frame(data)

  def mcgdbevt_thread(self,data):
    self.update_threads()
    super(ThreadsTable,self).mcgdbevt_frame(data)




class LocalvarsTable(ValueToChunks):
  def __init__(**kwargs):
    self.on_expand_variable(self.update_localvars)
    self.on_collapse_variable(self.update_localvars)
    self.on_change_slice(self.update_localvars)

  def process_connection(self):
    self.update_localvars()

  def update_localvars(self):
    lvars=self._get_local_vars()
    pkg={'cmd':'localvars','table':lvars}
    self.send(pkg)

  @exec_main
  def _get_local_vars(self):
    variables = self._get_local_vars_1 ()
    if len(variables)==0:
      return []
    lvars=[]
    funcname=self._get_frame_funcname(gdb.selected_frame())
    for name,value in variables.iteritems():
      chunks = self.value_to_chunks(value,name,funcname=funcname)
      check_chunks(chunks)
      col = {'chunks':chunks}
      row = {'columns':[col]}
      lvars.append(row)
    return {'rows':lvars}

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
              variables[name] = self.valcache(symbol.value(frame))
      if block.function:
        break
      block = block.superblock
    return variables

  def gdbevt_exited(self,evt):
    self.update_localvars()
  def gdbevt_stop(self,evt):
    self.update_localvars()
  def gdbevt_new_objfile(self,evt):
    self.update_localvars()
  def gdbevt_clear_objfiles(self,evt):
    self.update_localvars()
  def gdbevt_memory_changed(self,evt):
    self.update_localvars()
  def gdbevt_register_changed(self,evt):
    self.update_localvars()

  def shellcmd_frame_up(self):
    self.update_localvars()
  def shellcmd_frame_down(self):
    self.update_localvars()
  def shellcmd_thread(self):
    self.update_localvars()

  def mcgdbevt_frame(self,data):
    self.update_localvars()

  def mcgdbevt_thread(self,data):
    self.update_localvars()




class AuxWin(BaseWin):
  ''' Representation of window with localvars of current frame
  '''

  type='auxwin'
  startcmd='mcgdb open aux'

  def __init__(self, **kwargs):
    self.clear_caches()
    kwtab={'value_cache':self.value_cache, 'value_str_cache':self.value_str_cache}
    self.tables={
      'registers' : RegistersTable(**kwtab),
      'localvars' : LocalvarsTable(**kwtab),
      'backtrace' : BacktraceTable(**kwtab),
      'threads'   : ThreadsTable(**kwtab),
    }
    super(AuxWin,self).__init__(**kwargs)

  def clear_caches(self):
    self.value_cache={}
    self.value_str_cache()

  def process_connection(self):
    return super(AuxWin,self).process_connection()



  def gdb_check_breakpoint(self):
    pass
  def set_color(self,pkg):
    pass


  def gdbevt_stop(self,evt):
    self.clear_caches()

  def gdbevt_new_objfile(self,evt):
    self.clear_caches()

  def gdbevt_memory_changed(self,evt):
    self.clear_caches()

  def gdbevt_register_changed(self,evt):
    self.clear_caches()



