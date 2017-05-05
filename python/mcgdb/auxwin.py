#coding=utf8

import gdb

import re,sys,ctypes

from mcgdb.basewin import BaseWin
from mcgdb.common  import exec_in_main_pythread,gdb_stopped,inferior_alive,gdb_print
from mcgdb.basewin import stringify_value,valueaddress_to_ulong,stringify_value_safe, \
                          is_incomplete_type_ptr,check_chunks


class AuxWin(BaseWin):
  ''' Representation of window with localvars of current frame
  '''

  type='auxwin'
  startcmd='mcgdb open aux'

  def __init__(self, **kwargs):
    self.clear_caches()
    super(AuxWin,self).__init__(**kwargs)
    self.window_event_handlers.update({
      'onclick_data'    : self._onclick_data,
    })
    self.click_cmd_cbs={
      'select_frame'    : self._select_frame,
      'select_thread'   : self._select_thread,
      'change_variable' : self._change_variable,
      'change_slice'    : self._change_slice,
      'expand_variable' : self._expand_variable,
      'collapse_variable':self._collapse_variable,
    }
    self.converters={
      'bin_to_long' : self.bin_to_long,
      'hex_to_long' : lambda x: long(x,16),
    }
    self.regex_split = re.compile('\s*([^\s]+)\s+([^\s+]+)\s+(.*)')
    self.slice_regex=re.compile('^(-?\d+)([:, ](-?\d+))?$')

    self.regnames=[]
    self.user_slice={}
    self.expand_variable={}
    #grab register names
    regtab = gdb.execute('maint print registers',False,True).split('\n')[1:]
    for reg in regtab:
      if reg=="*1: Register type's name NULL.":
        continue
      reg=reg.split()
      if len(reg)>0 and reg[0] and reg[0]!="''" and len(reg[0])>0:
        self.regnames.append('$'+reg[0])

  def bin_to_long(self,str_bin):
    '''converst string-binary-representation of number to long'''
    return long(str_bin,2)

  def clear_caches(self):
    self.value_cache={}
    self.value_str_cache={}

  def process_connection(self):
    rc=super(AuxWin,self).process_connection()
    if rc:
      self.update_all()
    return rc


  def _onclick_data(self,pkg):
    click_cmd = pkg['data']['click_cmd']
    cb=self.click_cmd_cbs.get(click_cmd)
    if cb==None:
      return
    return cb(pkg)

  def _expand_variable(self,pkg):
    path=pkg['data']['path']
    funcname=pkg['data']['funcname']
    self.expand_variable[(funcname,path)]=True
    self.update_localvars()

  def _collapse_variable(self,pkg):
    path=pkg['data']['path']
    funcname=pkg['data']['funcname']
    self.expand_variable[(funcname,path)]=False
    self.update_localvars()



  def _change_slice_1(self,pkg):
    path=pkg['data']['path']
    funcname=pkg['data']['funcname']
    user_input = pkg['user_input']
    match=self.slice_regex.match(user_input)
    if match:
      grps=match.groups()
      n1=int(grps[0])
      if grps[2]!=None:
        n2=int(grps[2])
      else:
        n2=None
      if n2!=None and n1>=n2:
        self.send_error('bad input: right bound must be greater than left')
        return
      self.user_slice[(funcname,path)] = (n1,n2)
    else:
      self.send_error('bad input: {}'.format(user_input))
      return
    self.update_localvars()
    self.update_backtrace()

  def _change_slice(self,pkg):
    return self._change_slice_1(pkg)

  def _change_variable_1(self,pkg):
    if not gdb_stopped():
      self.send_error('inferior running')
      return None
    if not inferior_alive ():
      self.send_error('inferior not alive')
      return None
    data=pkg['data']
    path=data['path']
    user_input = pkg['user_input']
    value=self.valcache(path)
    if 'converter' in data:
      new_value = self.converters.get(data['converter'])(user_input)
    elif value.type.strip_typedefs().code in (gdb.TYPE_CODE_INT,gdb.TYPE_CODE_PTR):
      try:
        new_value=long(gdb.parse_and_eval(user_input))
      except Exception as e:
        self.send_error(str(e))
        return None
    else:
      new_value = user_input
    gdb_cmd='set variable {path}={new_value}'.format(path=path,new_value=new_value)
    try:
      exec_in_main_pythread(gdb.execute, (gdb_cmd,))
    except Exception as e:
      self.send_error(str(e))
      return None
    self.update_all()

  def _change_variable(self,pkg):
    res=exec_in_main_pythread(self._change_variable_1, (pkg,))
    self.update_all() #обновление будет осуществлятсья всегда, даже в случае
    #некорректно введенных данных. Поскольку после введения данных у пользователя
    #отображается <Wait change: ... >, и это сообщение надо заменить предыдущим значением.
    return res


  def _select_thread_1(self,nthread):
    threads=gdb.selected_inferior().threads()
    if len(threads)<nthread+1:
      return 'thread #{} not exists'.format(nthread)
    threads[nthread].switch()
    self.update_all()

  def _select_thread(self,pkg):
    nthread = pkg['data']['nthread']
    res=exec_in_main_pythread(self._select_thread_1, (nthread,))
    if res!=None:
      self.send_error(res)
    else:
      # имитируем, что пользователь вызвал в шелле команду, и оповещаем
      # об этом остальные сущности
      return [{'cmd':'shellcmd','cmdname':'thread'}]

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
        self.update_all()
        return
      n_cur_frame+=1
      frame = frame.older()
    return "can't find frame #{}".format(nframe)

  def _select_frame(self,pkg):
    nframe = pkg['data']['nframe']
    res=exec_in_main_pythread(self._select_frame_1, (nframe,))
    if res!=None:
      self.send_error(res)
    else:
      return [{'cmd':'shellcmd','cmdname':'frame'}]

  def update_localvars(self):
    lvars=self._get_local_vars()
    pkg={'cmd':'localvars','table':lvars}
    self.send(pkg)

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
  def update_registers(self):
    try:
      regs = self.get_registers()
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
  def update_threads(self):
    try:
      self.send({
        'cmd':'threads',
        'table':self.get_threads(),
      })
    except:
      return
  def gdb_check_breakpoint(self):
    pass
  def set_color(self,pkg):
    pass

  def _get_local_vars(self):
    #try:
    res=exec_in_main_pythread( self._get_local_vars_chunks, ())
    #except (gdb.error,RuntimeError):
      #import traceback
      #traceback.print_exc()
    #  res=[]
    return res

  def add_valcache_byaddr(self,value):
    addr=valueaddress_to_ulong(value.address)
    if addr==None:
      return False
    key=(addr,str(value.type))
    self.value_cache[key]=value
    return True

  def get_this_frame_num(self):
    frame=gdb.selected_frame()
    if frame==None:
      return None
    cnt=0
    while frame:
      cnt+=1
      try:
        frame=frame.newer()
      except gdb.error:
        #if gdb reached remote protocol timeout and can't read registers
        #then frame can be invalid.
        return None
    return cnt

  def cached_stringify_value(self,value,path,**kwargs):
    frnum=self.get_this_frame_num()
    if frnum==None:
      valcache=None
    else:
      key=(frnum,path)
      valcache=self.value_str_cache.get(key)
    if valcache==None:
      valcache=stringify_value_safe(value,**kwargs)
      self.value_str_cache[key]=valcache
    return valcache


  def valcache(self,value_or_path,**kwargs):
    '''return value from cache if exists else return argument value'''
    if type(value_or_path) in (str,unicode):
      path=value_or_path
      frnum=self.get_this_frame_num()
      th=gdb.selected_thread()
      if frnum==None or th==None:
        valcache1=None
      else:
        key=(frnum,path,th.global_num)
        valcache1=self.value_str_cache.get(key)
      if valcache1==None:
        valcache1=gdb.parse_and_eval(path)
        self.value_cache[key]=valcache1
        self.add_valcache_byaddr(valcache1)
    else:
      value=value_or_path
      addr=valueaddress_to_ulong(value.address)
      if addr==None:
        return value
      key=(addr,str(value.type))
      valcache1=self.value_cache.get(key)
      if valcache1==None:
        self.add_valcache_byaddr(value)
        valcache1=value
    return valcache1

  def make_subarray_name(self,value,valuepath,**kwargs):
    funcname = kwargs.get('funcname')
    n1,n2=self.user_slice.get((funcname,valuepath),(0,2))
    chunks = [{'str':'*(','name':'varname'}]+\
    self.changable_value_to_chunks(value,valuepath,**kwargs)+\
    [{'str':')','name':'varname'}]+\
    [self.make_slice_chunk(n1,n2,valuepath,funcname)]
    return chunks

  def is_array_fetchable(self,arr,n1,n2):
    '''Данная функция возвращает True, если элементы массива с номерами [n1,n2] включая концы
        доступны для чтения. False в противном случае.
        Прочитанные (fetch_lazy) значения массива будут сохранены в кэш.
    '''
    try:
      self.valcache(arr[n1]).fetch_lazy()
      if n2==None:
        return True
      self.valcache(arr[n2]).fetch_lazy()
      for i in range(n1+1,n2):
        self.valcache(arr[i]).fetch_lazy()
    except gdb.MemoryError:
      return False
    return True

  def array_to_chunks (self, value, name, n1, n2, path, deref_depth, **kwargs):
    ''' Конвертация массива или указателя, который указывает на массив в json-дерево.

        Args:
          n1 (int): Начиная с этого номера элементы массива будут напечатаны.
          n2 (int): включительно по этот номер будут напечатаны элементы массива.

        Если элементы массива не указатели, то печатается нечто вроде
        arr = [p1,p2,..,pn]
        Если элементы массива есть указатели, тип которых не "char *"
        и не "void *", то печатается конструкция вида
        arr = [
           *(p1) = [...]
           *(p2) = [...]
        ]
        Где p1,p2 есть адреса, а конструкция между  [...] есть содержимое указателя

    '''
    chunks=[]
    assert name!=None
    assert path
    funcname=kwargs.get('funcname')
    already_deref=kwargs.get('already_deref')
    arrloc=(funcname,path)

    type_code=value.type.strip_typedefs().code
    if name:
      if kwargs.get('print_typename',True):
        chunks+=self.value_type_to_chunks(value,**kwargs)
        chunks.append({'str':' '})

    if type(name) is str:
      slice_chunk = self.make_slice_chunk(n1,n2,path,funcname)
      varname=[
        {'str':name,'name':'varname'},
        slice_chunk,
      ]
      chunks+=varname
    else:
      chunks+=name
    chunks+=[{'str':' = '}]
    valueloc=(funcname,path)
    if type_code==gdb.TYPE_CODE_PTR:
      value_addr = ctypes.c_ulong(long(value)).value
    else:
      try:
        value_addr = value.address
      except gdb.MemoryError:
        value_addr=None
    is_already_deref = value_addr!=None and value_addr in already_deref
    max_deref_depth = kwargs.get('max_deref_depth',3)
    if  max_deref_depth!=None and \
        ((deref_depth>=kwargs.get('max_deref_depth',3) or is_already_deref) and not self.expand_variable.get((funcname,path))) or \
        (valueloc in self.expand_variable and not self.expand_variable[(funcname,path)] ):
      chunks += self.collapsed_array_to_chunks(path,**kwargs)
      return chunks

    if value_addr!=None:
      already_deref.add(value_addr)

    chunks1=[]
    array_data_chunks=[]
    n22 = n2+1 if n2!=None else n1+1
    deref_value = value[n1]
    deref_type_code = deref_value.type.strip_typedefs().code
    deref_type_str  = str(deref_value.type.strip_typedefs())
    if deref_type_code==gdb.TYPE_CODE_PTR and not re.match('.*((char \*)|(void \*))$',deref_type_str) and not is_incomplete_type_ptr(deref_value):
      name_lambda = lambda value,valuepath,**kwargs : self.make_subarray_name(value,valuepath,**kwargs)
      elem_as_array=True
    else:
      name_lambda = lambda value,valuepath,**kwargs : None
      elem_as_array=False

    arr_elem_size=deref_value.type.strip_typedefs().sizeof
    arr_size=n2-n1+1 if n2!=None else 1
    #if value_addr==None or self.possible_read_memory(value_addr,arr_elem_size*arr_size):
    if value_addr==None or self.is_array_fetchable(value,n1,n2):
      if 'delimiter' in kwargs:
        delimiter=kwargs['delimiter']
      else:
        if deref_type_code in (gdb.TYPE_CODE_INT,gdb.TYPE_CODE_FLT):
          delimiter={'str':', '}
        else:
          delimiter={'str':',\n'}
      for i in range(n1,n22):
        path_idx = '{path}[{idx}]'.format(path=path,idx=i)
        value_idx = self.valcache(value[i])
        value_idx_name = name_lambda(value_idx,path_idx,**kwargs)
        if elem_as_array:
          array_data_chunks+=self.pointer_data_to_chunks(value_idx,value_idx_name,path_idx,deref_depth,**kwargs)
        else:
          array_data_chunks+=self.value_to_chunks_1(value_idx,value_idx_name,path_idx,deref_depth,**kwargs)
        if delimiter and i!=n22-1:
          array_data_chunks.append(delimiter)
      array_data_chunks.append({'str':'\n'})
      chunks1.append({'chunks':array_data_chunks,'type_code':'TYPE_CODE_ARRAY'})
      chunks.append({
        'str':'[\n',
        'onclick_data':self.base_onclick_data('collapse_variable',funcname=funcname,path=path)
      })
      chunks.append ({
        'chunks'  : chunks1,
        'name'    : 'parenthesis',
      })
      chunks.append({
        'str':'\n]\n',
        'onclick_data':self.base_onclick_data('collapse_variable',funcname=funcname,path=path)
      })
    else:
      chunks.append({'str':'[CantAccsMem]'})
    return chunks

  def base_onclick_data(self,cmdname,**kwargs):
    onclick_data = {
      'click_cmd':cmdname,
    }
    onclick_data.update(kwargs)
    return onclick_data

  def collapsed_struct_to_chunks(self,path, **kwargs):
    return self.collapsed_item_to_chunks(path,'{<Expand>}', **kwargs)

  def collapsed_array_to_chunks(self,path, **kwargs):
    return self.collapsed_item_to_chunks(path,'[<Expand>]', **kwargs)


  def collapsed_item_to_chunks(self,path,collapsed_str,**kwargs):
    return [{
        'str':collapsed_str,
        'onclick_data':self.base_onclick_data('expand_variable',path=path,funcname=kwargs.get('funcname')),
      }]


  def pointer_data_to_chunks (self,value,name,path,deref_depth, **kwargs):
    str_type = str(value.type.strip_typedefs())
    assert not re.match('.*void \*$',str_type)
    assert not is_incomplete_type_ptr(value)
    if  kwargs.get('disable_dereference') :
      return []
    if value.is_optimized_out:
      return self.name_to_chunks(name)+[{'str':'<OptimizedOut>'}]
    funcname=kwargs.get('funcname')
    chunks=[]
    if funcname and self.user_slice.get((funcname,path)):
      n1,n2 = self.user_slice.get((funcname,path))
    else:
      deref_type_code = value.dereference().type.strip_typedefs().code
      if deref_type_code in (gdb.TYPE_CODE_STRUCT,gdb.TYPE_CODE_UNION,gdb.TYPE_CODE_FUNC):
        n1,n2=(0,None)
      else:
        n1,n2=(0,2)
    chunks+=self.array_to_chunks(value,name,n1,n2,path,deref_depth+1, **kwargs)
    return chunks


  def pointer_to_chunks (self, value, name, path, deref_depth, **kwargs):
    chunks=[]
    if name:
      if kwargs.get('print_typename',True):
        chunks+=self.value_type_to_chunks(value,**kwargs)
        chunks.append({'str':' '})
      chunks+=self.name_to_chunks(name)
    chunks += self.changable_value_to_chunks(value,path,**kwargs)
    return chunks

  def name_to_chunks(self,name,**kwargs):
    with_equal=kwargs.get('with_equal',True)
    chunks=[]
    if name!=None:
      if type(name) is str:
        chunks+=[{'str':name, 'name':'varname'},]
      else:
        chunks+=name
      if with_equal:
        chunks+=[{'str':' = '}]
    return chunks

  def changable_value_to_chunks(self,value,path,**kwargs):
    if kwargs.get('enable_additional_text',False)==True:
      valuestr  = self.cached_stringify_value(value,path,**kwargs)
    else:
      valuestr  = stringify_value(value,**kwargs)
    if 'proposed_text' not in kwargs:
      kwargs['enable_additional_text']=False
      strvalue_pure=stringify_value(value,**kwargs)
      kwargs['proposed_text'] = strvalue_pure
    valuetype1 = str(value.type)
    valuetype2 = str(value.type.strip_typedefs())
    if valuetype1==valuetype2:
      valuetype=valuetype1
    else:
      valuetype='{} aka {}'.format(valuetype1,valuetype2)
    return self.changable_strvalue_to_chunks(valuestr,path,valuetype,**kwargs)

  def changable_strvalue_to_chunks(self,valuestr,path,valuetype,**kwargs):
    onclick_data={
      'click_cmd':'change_variable',
      'path':path,
      'input_text': '{type} {path}'.format(path=path,type=valuetype),
    }
    if 'converter' in kwargs:
      onclick_data['converter']=kwargs['converter']
    res={'str':valuestr,'name':'varvalue', 'onclick_data':onclick_data, 'onclick_user_input':True}
    if 'proposed_text' in kwargs:
      res['proposed_text']=kwargs['proposed_text']
    return [res]



  def struct_to_chunks(self,value,name,path,deref_depth, **kwargs):
    already_deref = kwargs['already_deref']
    type_code = value.type.strip_typedefs().code
    chunks=[]
    if name:
      if kwargs.get('print_typename',True):
        chunks+=self.value_type_to_chunks(value,**kwargs)
        chunks.append({'str':' '})
      chunks+=self.name_to_chunks(name)
    funcname=kwargs.get('funcname')
    valueloc=(funcname,path)
    #try:
    value_addr = value.address
    #except gdb.MemoryError:
    #  value_addr=None
    is_already_deref = value_addr!=None and value_addr in already_deref
    max_deref_depth = kwargs.get('max_deref_depth',3)
    if  max_deref_depth!=None and \
        ((deref_depth>=max_deref_depth or is_already_deref) and not self.expand_variable.get((funcname,path))) or \
        (valueloc in self.expand_variable and not self.expand_variable[(funcname,path)] ):
      chunks += self.collapsed_struct_to_chunks(path, **kwargs)
      return chunks

    if value_addr!=None:
      already_deref.add(value_addr)

    chunks1=[]
    data_chunks=[]
    for field in value.type.strip_typedefs().fields():
      field_name = field.name
      field_value = self.valcache(value[field_name])
      value_path='{path}.{field_name}'.format(path=path,field_name=field_name)
      data_chunks+=self.value_to_chunks_1(field_value,field_name,value_path,deref_depth,**kwargs)
      data_chunks.append({'str':'\n'})
    if type_code==gdb.TYPE_CODE_STRUCT:
      chunks1.append({'chunks':data_chunks,'type_code':'TYPE_CODE_STRUCT'})
    elif type_code==gdb.TYPE_CODE_UNION:
      chunks1.append({'chunks':data_chunks,'type_code':'TYPE_CODE_UNION'})
    chunks.append({
      'str':'{\n',
      'onclick_data':self.base_onclick_data('collapse_variable',funcname=funcname,path=path),
    })
    chunks.append ({
      'chunks'  : chunks1,
    })
    chunks.append({
      'str':'\n}\n',
      'onclick_data':self.base_onclick_data('collapse_variable',funcname=funcname,path=path),
    })
    return chunks



  def value_to_chunks(self,value,name=None,**kwargs):
    ''' Конвертирование gdb.Value в json-дерево.

        Args:
            value (gdb.Value): значение, которое нужно сконвертировать в json
            name (str): Имя, которое используется для печати NAME = VALUE. Если не задано,
                то напечатается просто VALUE.
            **funcname (str): имя функции, в контексте которой value конвертируется в json.
            **max_deref_depth (int, default=3): Данный параметр используется для ограничения dereference указателей.
                В рамках преобразования, которое делает данная функция для каждого указателя будет напечатан не только
                адрес, но и значение памяти. Если представить список из миллиона элементов, то, очевидно, что весь
                список печатать не надо.
            **already_deref (set): множество, состоящее из целых чисел. Кадое число трактуется, как адрес.
                Для каждого адреса из данного множества разыменование производиться не будет.
            **print_typename (bool): True-->типы печатаются False-->не печатаются.
    '''
    path=name
    deref_depth=0
    already_deref = set()
    if 'funcname' not in kwargs:
      kwargs['funcname'] = self._get_frame_funcname(gdb.selected_frame())
    if 'already_deref' not in kwargs:
      kwargs['already_deref'] = set()
    if 'max_deref_depth' not in kwargs:
      kwargs['max_deref_depth']=0
    return self.value_to_chunks_1(value,name,path,deref_depth,**kwargs)

  def value_withstr_to_chunks(self,value,name,path,deref_depth,**kwargs):
    chunks=[]
    chunks+=self.name_to_chunks(name)
    chunks.append({'str':self.cached_stringify_value(value,path,enable_additional_text=True), 'name':'varvalue'})
    #chunks+=self.value_to_str_chunks(value,path,enable_additional_text=True,**kwargs)
    return chunks

  def possible_read_memory_ptr(self,value,**kwargs):
    assert value.type.strip_typedefs().code==gdb.TYPE_CODE_PTR
    n1=kwargs.get('n1',0)
    addr=ctypes.c_ulong(long(value)).value
    size=value.dereference().type.strip_typedefs().sizeof
    return self.possible_read_memory(addr+n1*size,size)

  def possible_read_memory(self,addr,size):
    if addr<0:
      return False
    infer = gdb.selected_inferior ()
    if infer==None:
      return False
    try:
      infer.read_memory (addr,size)
      return True
    except gdb.MemoryError:
      return False

  def ptrval_to_ulong(self,value):
    return ctypes.c_ulong(long(value)).value

  def functionptr_to_chunks(self,value, name, path, deref_depth, **kwargs):
    chunks=[]
    func_addr = self.ptrval_to_ulong(value)
    function=None
    try:
      block=gdb.block_for_pc (func_addr)
    except RuntimeError:
      block=None
    while block:
      if block.function:
        function = block.function
        break
      block=block.superblock
    if function:
      func_name=function.name
    else:
      func_name='unknown'
    if name:
      if kwargs.get('print_typename',True):
        chunks+=self.value_type_to_chunks(value,**kwargs)
        chunks.append({'str':' '})
      chunks+=self.name_to_chunks(name)
    #chunks.append({'str':hex(func_addr)[:-1]})
    chunks+=self.changable_value_to_chunks(value,path,**kwargs)
    chunks.append({'str':' '})
    chunks.append({'str':'<{}>'.format(func_name)})
    return chunks



  def functionptr_to_chunks_argtypes(self,value, name, path, deref_depth, **kwargs):
    arg_types = [field.type for field in value.dereference().type.strip_typedefs().fields()]
    return_type = value.dereference().type.strip_typedefs().target()
    func_addr = self.ptrval_to_ulong(value)
    func_name='unknown'
    try:
      block=gdb.block_for_pc (func_addr)
    except RuntimeError:
      block=None
    while block:
      if block.function:
        func_name = block.function.name
        break
      block=block.superblock
    chunks=[]
    chunks.append({'str':'{'})
    chunks.append({'str':str(return_type),'name':'datatype'})
    chunks.append({'str':' '})
    chunks.append({'str':'('})
    arg_chunks=[{'str':str(arg_type),'name':'datatype'} for arg_type in arg_types]
    if len(arg_chunks)>0:
      arg_chunks_commas=[]
      arg_chunks_commas.append(arg_chunks[0])
      for arg_chunk in arg_chunks[1:]:
        arg_chunks_commas.append({'str':','})
        arg_chunks_commas.append(arg_chunk)
      chunks+=arg_chunks_commas
    chunks.append({'str':')'})
    chunks.append({'str':'}'})
    chunks.append({'str':' '})
    chunks.append({'str':hex(func_addr)[:-1]})
    chunks.append({'str':' '})
    chunks.append({'str':'<{}>'.format(func_name)})
    return chunks

  def value_type_to_chunks(self,value,**kwargs):
    type_code=value.type.strip_typedefs().code
    if type_code==gdb.TYPE_CODE_STRUCT:
      return [{'str':'struct','name':'datatype'}]
    elif type_code==gdb.TYPE_CODE_UNION:
      return [{'str':'union','name':'datatype'}]
    else:
      return [{'str':str(value.type),'name':'datatype'}]

  def value_to_chunks_1(self,value,name,path,deref_depth,**kwargs):
    ''' Конвертирование gdb.Value в json-дерево. Рекурсия.
        Дополнительное описание см. в функции `value_to_chunks`

        Args:
            path_parent (str): Используется для определения местонахождения переменной.
                Напр., рассмотр. структуру s, которая сод. структуру y. s={x:1,y:{a:5,b:2}, arr[2] = {A0,A1} }
                При печати структуры y ей будет передан path_parent='s'. На основе
                path_parent будет сформирован path у дочерних полей. Напри., s.y.a будет иметь path
                "s.y.a", для элемента массива A1 path = "s.arr[1]"
            path_name (str): Применяется для формирования path. Совпадает с именем переменной, за исключением
                элементов массивов. Для A0 path_name будет arr[0]. Для массива arr path_name="arr".
            deref_depth (int): текущая глубина разыменования. Если deref_depth==max_deref_depth, то указатель
                будет напечатан без разыменования.
            **deref_depth_max (int): см. deref_depth
            **already_deref (set): мн-во указателей, которые уже были разменованы. Если была напечатана структура или массив,
                которая определена статически, то будет взят адрес данной структуры и помещен в данное множество.
                Рассмотрим двунапр. данное мн-во
                предотвр. ситуацию, когда процесс разыменования дошел до конца списка, а потом начал разыменовывать указатели
                на предыдущие элементы, потом вновь разыменовывать next-элементы....
            **disable_dereference (bool): Если True, то dereference делаться не будет. По умолчанию False.

    '''
    chunks=[]
    type_code = value.type.strip_typedefs().code
    type_str = str(value.type.strip_typedefs())
    funcname=kwargs.get('funcname')
    print_typename=kwargs.get('print_typename',True)
    if type_code in (gdb.TYPE_CODE_STRUCT,gdb.TYPE_CODE_UNION):
      chunks+=self.struct_to_chunks(value,name,path,deref_depth,**kwargs)
    elif type_code==gdb.TYPE_CODE_ARRAY:
      array_addr = value.address
      if array_addr!=None:
        pointer_chunks = self.pointer_to_chunks (array_addr, name, path, deref_depth, **kwargs)
        if len(pointer_chunks)!=0:
          chunks+=pointer_chunks
          chunks.append({'str':'\n'})
      if re.match('.*char \[.*\]$',type_str):
        chunks+=self.value_withstr_to_chunks(value,name,path,deref_depth,**kwargs)
      else:
        n1_orig,n2_orig = value.type.strip_typedefs().range()
        funcname=kwargs['funcname']
        user_slice = self.user_slice.get((funcname,path))
        if user_slice:
          n1,n2 = user_slice
          n1 = max(n1,n1_orig)
          if n2!=None:
            n2 = min(n2,n2_orig)
        else:
          n1,n2 = n1_orig,n2_orig
        chunks += self.array_to_chunks (value, name, n1, n2, path, deref_depth, **kwargs)
    elif type_code==gdb.TYPE_CODE_PTR:
      if re.match('.*char \*$',type_str):
        #строку печатаем по-другому в сравнении с обычным pointer
        if name:
          if print_typename:
            chunks+=self.value_type_to_chunks(value,**kwargs)
            chunks.append({'str':' '})
          chunks+=self.name_to_chunks(name)
        chunks+=self.changable_value_to_chunks(value,path,enable_additional_text=True,**kwargs)
      else:
        is_funct_ptr=False
        pointer_data_chunks = []
        if not value.is_optimized_out and not re.match('.*void \*$',type_str) and not is_incomplete_type_ptr(value):
          #все OK
          if value.dereference().type.strip_typedefs().code==gdb.TYPE_CODE_FUNC:
            is_funct_ptr=True
          else:
            pointer_data_chunks = self.pointer_data_to_chunks (value, name, path, deref_depth, **kwargs)
        if is_funct_ptr:
          pointer_chunks = self.functionptr_to_chunks(value, name, path, deref_depth, **kwargs)
        else:
          pointer_chunks = self.pointer_to_chunks (value, name, path, deref_depth, **kwargs)
        chunks+=pointer_chunks
        if len(pointer_data_chunks) > 0:
          chunks+=[{'str':'\n'}]
          chunks+=pointer_data_chunks
    else:
      if  name!=None:
        if print_typename:
          chunks+=self.value_type_to_chunks(value,**kwargs)
        chunks.append({'str':' '})
        chunks+=self.name_to_chunks(name)
      chunks+=self.changable_value_to_chunks(value,path,**kwargs)
    return chunks

  def make_slice_chunk_auto(self,path,funcname):
    n1,n2 = self.user_slice.get((funcname,path),(0,None))
    return self.make_slice_chunk(n1,n2,path,funcname)

  def make_slice_chunk(self,n1,n2,path,funcname):
    chunks=[]
    chunks.append({'str':'[','name':'slice'})
    if n2==None:
      chunks.append({'str':str(n1),'name':'slice'})
    else:
      chunks.append({'str':str(n1),   'name':'slice'})
      chunks.append({'str':':',                  'name':'slice'})
      chunks.append({'str':str(n2),  'name':'slice'})
    chunks.append({'str':']','name':'slice'})
    onclick_data={
      'click_cmd':'change_slice',
      'path':path,
      'funcname':funcname,
      'input_text':'enter new slice N or N:M',
    }
    slice_chunk={
      'chunks':chunks,
      'onclick_data':onclick_data,
      'onclick_user_input':True,
    }
    return slice_chunk

  def _get_local_vars_chunks(self):
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
    #lvars.sort( cmp = lambda x,y: 1 if x[''][0][0]['str']>y[0][0]['str'] else -1 )
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

  def _get_stack_1(self):
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

  def get_stack(self):
    return exec_in_main_pythread (self._get_stack_1,())

  def integer_as_struct_chunks(self,value,name,**kwargs):
    '''Данная функция предназначается для печати целочисленного
        регистра, как структуру с полями dec,hex,bin
    '''
    chunks=[]
    if kwargs.get('print_typename',True):
      chunks+=self.value_type_to_chunks(value)
      chunks.append({'str':' '})
    chunks+=self.name_to_chunks(name)
    data_chunks=[]
    data_chunks += self.name_to_chunks('dec')
    data_chunks += self.changable_value_to_chunks(value,name, integer_mode='dec')
    data_chunks += [{'str':'\n'}]
    data_chunks += self.name_to_chunks('hex')
    data_chunks += self.changable_value_to_chunks(value,name, integer_mode='hex',converter='hex_to_long')
    data_chunks += [{'str':'\n'}]
    data_chunks += self.name_to_chunks('bin')
    data_chunks += self.changable_value_to_chunks(value,name, integer_mode='bin',converter='bin_to_long')
    data_chunks += [{'str':'\n'}]
    data_chunks += [{'str':'\n'}]
    chunks.append({'str':'{\n',})
    chunks+=[{'chunks':data_chunks,'type_code':'TYPE_CODE_STRUCT'}]
    chunks.append({'str':'}\n',})
    return chunks

  def _get_regs_1(self):
    rows_regs=[]
    for regname in self.regnames:
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
      col  = {'chunks' : chunks}
      row  = {'columns' : [col]}
      rows_regs.append(row)
    return {'rows' : rows_regs}

  def get_registers(self):
    if not gdb_stopped() or not inferior_alive ():
      return
    return exec_in_main_pythread (self._get_regs_1,())

  def _get_threads_1(self):
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

  def get_threads(self):
    return exec_in_main_pythread (self._get_threads_1,())

  def update_all(self):
    self.update_localvars()
    self.update_backtrace()
    self.update_registers()
    self.update_threads()


  def gdbevt_exited(self,evt):
    self.update_all()

  def gdbevt_stop(self,evt):
    self.clear_caches()
    self.update_all()

  def gdbevt_new_objfile(self,evt):
    self.clear_caches()
    self.update_all()

  def gdbevt_clear_objfiles(self,evt):
    self.update_all()

  def gdbevt_memory_changed(self,evt):
    self.clear_caches()
    self.update_localvars()
    self.update_registers()

  def gdbevt_register_changed(self,evt):
    self.clear_caches()
    self.update_localvars()
    self.update_registers()


  def shellcmd_frame_up(self):
    self.update_all()
  def shellcmd_frame_down(self):
    self.update_all()
  def shellcmd_frame(self):
    self.update_all()
  def shellcmd_thread(self):
    self.update_all()
  def shellcmd_thread(self):
    self.update_all()
