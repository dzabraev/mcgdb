#coding=utf8

import gdb
import re, ctypes
from abc import abstractmethod, abstractproperty


from mcgdb.common import    exec_main, gdb_print, gdb_stopped, \
                            inferior_alive, cached_stringify_value, \
                            valcache, stringify_value, \
                            get_this_thread_num, get_this_frame_num

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

class ValueToChunks(object):
  def __init__(self,INDEX, **kwargs):
    self.slice_regex=re.compile('^(-?\d+)([:, ](-?\d+))?$')
    self.user_slice={}
    self.expand_variable={}
    self.converters={}
    self.INDEX=INDEX
    self.converters['bin_to_long'] = lambda x: long(x,2)
    self.converters['hex_to_long'] = lambda x: long(x,16)
    self.path_id_thread_depend = kwargs.pop('thread_depend',True)
    self.path_id_frame_depend  = kwargs.pop('frame_depend',True)
    self.on_cbs={
      'expand_variable':    [],
      'collapse_variable':  [],
      'change_slice'    :   [],
      'change_variable' :   [],
    }


  def text_chunk(self,string,**kwargs):
    d=kwargs
    d.update({'str':string})
    return d

  def path_id(self,path,value=None):
    key=[]
    if self.path_id_thread_depend:
      key.append(get_this_thread_num())
    if self.path_id_frame_depend:
      key.append(get_this_frame_num())
    key.append(path)
    key=tuple(key)
    if value!=None:
      return self.INDEX(key,value)
    else:
      idx=self.INDEX.get(key)[0]
      assert idx!=None
      return idx

  def onclick_expand_variable(self,pkg):
    path=pkg['path']
    funcname=pkg['funcname']
    self.expand_variable[(funcname,path)]=True

  def onclick_collapse_variable(self,pkg):
    path=pkg['path']
    funcname=pkg['funcname']
    self.expand_variable[(funcname,path)]=False

  def onclick_change_slice(self,pkg):
    path=pkg['path']
    funcname=pkg['funcname']
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

  @exec_main
  def onclick_change_variable(self,pkg):
    #В случае некорректно введенных данных будет осуществляться обновл. переменных.
    #Поскольку после введения данных у пользователя
    #отображается <Wait change: ... >, и это сообщение надо заменить предыдущим значением.
    if not gdb_stopped():
      self.send_error('inferior running')
      return None
    if not inferior_alive ():
      self.send_error('inferior not alive')
      return None
    path=pkg['path']
    user_input = pkg['user_input']
    value=valcache(path)
    if 'converter' in pkg:
      new_value = self.converters.get(pkg['converter'])(user_input)
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
      gdb.execute(gdb_cmd)
    except Exception as e:
      self.send_error(str(e))
      return None
    #при изменении переменной будет сгенерировано событие
    #gdb.events.memory_changed. При обработке данного события
    #должны быть обновлены переменные.

  @abstractproperty
  def subentity_name(self):
    pass

  def base_onclick_data(self,cmdname,**kwargs):
    onclick_data = {
      'cmd' : 'onclick',
      'onclick' : cmdname,
      'subentity_dst' : self.subentity_name,
    }
    onclick_data.update(kwargs)
    return onclick_data


  def make_subarray_name(self,value,valuepath,**kwargs):
    funcname = kwargs.get('funcname')
    n1,n2=self.user_slice.get((funcname,valuepath),(0,2))
    slice_chunk=self.make_slice_chunk(n1,n2,valuepath,funcname)
    
    chunks = [{'str':'*(','name':'varname'}]+\
    self.changable_value_to_chunks(value,valuepath,**kwargs)+\
    [{'str':')','name':'varname'}]+\
    [slice_chunk]
    return chunks

  def is_array_fetchable(self,arr,n1,n2):
    '''Данная функция возвращает True, если элементы массива с номерами [n1,n2] включая концы
        доступны для чтения. False в противном случае.
        Прочитанные (fetch_lazy) значения массива будут сохранены в кэш.
    '''
    try:
      valcache(arr[n1]).fetch_lazy()
      if n2==None:
        return True
      valcache(arr[n2]).fetch_lazy()
      for i in range(n1+1,n2):
        valcache(arr[i]).fetch_lazy()
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
        value_idx = valcache(value[i])
        self.path_id(path_idx,value_idx)
        value_idx_name = name_lambda(value_idx,path_idx,**kwargs)
        if elem_as_array:
          array_data_chunks__1=self.pointer_data_to_chunks(value_idx,value_idx_name,path_idx,deref_depth,**kwargs)
        else:
          array_data_chunks__1=self.value_to_chunks_1(value_idx,value_idx_name,path_idx,deref_depth,**kwargs)
        array_data_chunks.append({'chunks':array_data_chunks__1,'id':self.path_id(path_idx,value_idx)})
        if delimiter and i!=n22-1:
          array_data_chunks.append(delimiter)
      array_data_chunks.append({'str':'\n'})
      chunks1.append({'chunks':array_data_chunks,'type_code':'TYPE_CODE_ARRAY'})
      chunks.append({
        'str':'[\n',
        'onclick_data':self.base_onclick_data('collapse_variable',funcname=funcname,path=path,parent_id=self.path_id(path))
      })
      chunks.append ({
        'chunks'  : chunks1,
        'name'    : 'parenthesis',
      })
      chunks.append({
        'str':'\n]\n',
        'onclick_data':self.base_onclick_data('collapse_variable',funcname=funcname,path=path,parent_id=self.path_id(path))
      })
    else:
      chunks.append({'str':'[CantAccsMem]'})
    return chunks

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


  def collapsed_struct_to_chunks(self,path, **kwargs):
    return self.collapsed_item_to_chunks(path,'{<Expand>}', **kwargs)

  def collapsed_array_to_chunks(self,path, **kwargs):
    return self.collapsed_item_to_chunks(path,'[<Expand>]', **kwargs)


  def collapsed_item_to_chunks(self,path,collapsed_str,**kwargs):
    return [{
        'str':collapsed_str,
        'onclick_data':self.base_onclick_data(
          'expand_variable',
          path=path,
          funcname=kwargs.get('funcname'),
          parent_id=self.path_id(path),
        ),
      }]

  def changable_value_to_chunks(self,value,path,**kwargs):
    if kwargs.get('enable_additional_text',False)==True:
      valuestr  = cached_stringify_value(value,path,**kwargs)
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
      'cmd':'onclick',
      'onclick':'change_variable',
      'path':path,
      'input_text': '{type} {path}'.format(path=path,type=valuetype),
      'parent_id' : self.path_id(path),
      'subentity_dst' : self.subentity_name,
    }
    if 'converter' in kwargs:
      onclick_data['converter']=kwargs['converter']
    res={'str':valuestr,'name':'varvalue', 'onclick_data':onclick_data, 'onclick_user_input':True}
    if 'proposed_text' in kwargs:
      res['proposed_text']=kwargs['proposed_text']
#    index_name = kwargs.get('index_name')
#    if index_name!=None:
#      res['id'] = self.INDEX(index_name)
#    else:
#      index_name=(path,valuetype)
#      res['id'] = INDEX(index_name)
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
      field_value = valcache(value[field_name])
      value_path='{path}.{field_name}'.format(path=path,field_name=field_name)
      data_chunks+=self.value_to_chunks_1(field_value,field_name,value_path,deref_depth,**kwargs)
      data_chunks.append({'str':'\n'})
    if type_code==gdb.TYPE_CODE_STRUCT:
      chunks1.append({'chunks':data_chunks,'type_code':'TYPE_CODE_STRUCT'})
    elif type_code==gdb.TYPE_CODE_UNION:
      chunks1.append({'chunks':data_chunks,'type_code':'TYPE_CODE_UNION'})
    chunks.append({
      'str':'{\n',
      'onclick_data':self.base_onclick_data('collapse_variable',funcname=funcname,path=path,parent_id=self.path_id(path)),
    })
    chunks.append ({
      'chunks'  : chunks1,
    })
    chunks.append({
      'str':'\n}\n',
      'onclick_data':self.base_onclick_data('collapse_variable',funcname=funcname,path=path,parent_id=self.path_id(path)),
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
    chunks.append({'str':cached_stringify_value(value,path,enable_additional_text=True), 'name':'varvalue'})
    #chunks+=self.value_to_str_chunks(value,path,enable_additional_text=True,**kwargs)
    return chunks

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
                При печати структуры ей будет передан path_parent='s'. На основе
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
    self.path_id(path,value)
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
    res_chunk={'chunks':chunks, 'id':self.path_id(path)}
    return [res_chunk]

#  def make_slice_chunk_auto(self,path,funcname):
#    n1,n2 = self.user_slice.get((funcname,path),(0,None))
#    return self.make_slice_chunk(n1,n2,path,funcname)

  def make_slice_chunk(self,n1,n2,path,funcname):
    chunks=[]
    chunks.append({'str':'[','name':'slice'})
    if n2==None:
      chunks.append({'str':str(n1), 'name':'slice'})
    else:
      chunks.append({'str':str(n1), 'name':'slice'})
      chunks.append({'str':':',     'name':'slice'})
      chunks.append({'str':str(n2), 'name':'slice'})
    chunks.append({'str':']','name':'slice'})
    onclick_data={
      'cmd':'onclick',
      'onclick':'change_slice',
      'path':path,
      'funcname':funcname,
      'input_text':'enter new slice N or N:M',
      'parent_id' : self.path_id(path),
      'subentity_dst' : self.subentity_name,
    }
    slice_chunk={
      'chunks':chunks,
      'onclick_data':onclick_data,
      'onclick_user_input':True,
    }
    return slice_chunk

  def integer_as_struct_chunks(self,value,name,**kwargs):
    return self.integer_as_struct_chunks_1(value,name,name,**kwargs)

  def integer_as_struct_chunks_1(self,value,name,path,**kwargs):
    '''Данная функция предназначается для печати целочисленного
        регистра, как структуру с полями dec,hex,bin
    '''
    self.path_id(path,value)
    chunks=[]
    if kwargs.get('print_typename',True):
      chunks+=self.value_type_to_chunks(value)
      chunks.append({'str':' '})
    chunks+=self.name_to_chunks(name)
    data_chunks=[]
    data_chunks += self.name_to_chunks('dec')
    data_chunks += self.changable_value_to_chunks(value,path,integer_mode='dec',index_name=path+'_dec')
    data_chunks += [{'str':'\n'}]
    data_chunks += self.name_to_chunks('hex')
    data_chunks += self.changable_value_to_chunks(value,path,integer_mode='hex',converter='hex_to_long',index_name=path+'_hex')
    data_chunks += [{'str':'\n'}]
    data_chunks += self.name_to_chunks('bin')
    data_chunks += self.changable_value_to_chunks(value,path,integer_mode='bin',converter='bin_to_long',index_name=path+'_bin')
    data_chunks += [{'str':'\n'}]
    data_chunks += [{'str':'\n'}]
    chunks.append({'str':'{\n',})
    chunks+=[{'chunks':data_chunks,'type_code':'TYPE_CODE_STRUCT'}]
    chunks.append({'str':'}\n',})
    return [{'chunks':chunks, 'id':self.path_id(path)}]

  def _get_frame_func_args(self,frame):
      args=[]
      try:
        block=frame.block()
      except RuntimeError:
        return []
      while block:
        for sym in block:
          if sym.is_argument:
            value = valcache(sym.value(frame))
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
      elif 'chunks' in chunk:
        ok+=self.filter_chunks_with_id(chunk['chunks'])
    return ok




