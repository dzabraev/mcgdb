#coding=utf8

import gdb
import re, ctypes, copy
from abc import abstractmethod, abstractproperty


from mcgdb.common import    exec_main, gdb_print, gdb_stopped, \
                            inferior_alive, cached_stringify_value, \
                            valcache, stringify_value, \
                            get_this_thread_num, get_this_frame_num, \
                            mcgdbBaseException, INDEX



class Node(object):
  ''' Данный класс используется для представления пути до переменной
      Например, this[0].cpzero или this[0]._vptr.Cache
      Данный класс был создан для обработки путей типа this[0]._vptr.Cache.
      Особенность this[0]._vptr.Cache в том, что пути this[0]._vptr не существует,
      а this[0]._vptr.Cache существует
  '''
  def __init__(self,name,parent,base=None):
    self.name=name
    self.parent=parent
    if base:
      self.base=base
    else:
      self.base=parent.base
    self.childs={}
    self.base.id_seq+=1
    self.id=self.base.id_seq
    self.base.nodes[self.id] = self
    if self.parent:
      self.do_capture()
      self.parent.childs[name]=self

  def do_capture(self):
    self.saved_img =self.get_value_img(self.value())
    self.saved_data = self.base.capture(self.id)

  def get_value_img(self,value):
    try:
      return unicode(value)
    except Exception as e:
      return str(e)

  def is_changed_upd(self):
    old_img  = self.saved_img
    old_data = self.saved_data
    self.do_capture() #update saved_{img,data}
    new_img  = self.saved_img
    new_data = self.saved_data
    return not self.base.equals(old_img,old_data,new_img,new_data)

  def append(self,name,tochunks=None):
    ''' Если name является строкой, то xxx.name; если name есть int, то будет xxx[name]
        Данный метод возвращает новый Path, где к новому объекту добавлен name
    '''
    if not type(name) is int:
      name = name.strip()
    child = self.childs.get(name)
    if child:
      child.do_capture()
    else:
      child = Node(name=name,parent=self)
    child.tochunks=tochunks
    return child

  def path_from_root(self):
    assert self.parent!=None
    s=[self.name]
    parent=self.parent
    #в корне дерева ничего не хранится, поэтому parent.parent
    while parent.parent:
      s.append(parent.name)
      parent=parent.parent
    s.reverse()
    return s

  def __str__(self):
    ''' Вернуть значение path в печатном виде'''
    parent=self.parent
    path=self.path_from_root()
    strpath=path[0]
    assert type(path[0]) is str
    for name in path[1:]:
      if type(name) is int:
        #берется элемент массива ptr[0]
        strpath = '{}[{}]'.format(strpath,name)
      else:
        strpath = strpath+'.'+name
    return strpath

  def value(self):
    ''' Вернуть gdb.Value, которое соответствует path'''
    path=self.path_from_root()
    value = gdb.parse_and_eval(path[0])
    for name in path[1:]:
      value = value[name]
    return valcache(value)

  def assign(self,new_value):
    gdb_cmd='set variable {path}={new_value}'.format(path=str(self),new_value=new_value)
    try:
      gdb.execute(gdb_cmd)
    except Exception as e:
      raise mcgdbBaseException(str(e))


class BasePath(object):
  def __init__(self, capture, equals):
    self.nodes={} # nodes[path_id] = node
    self.id_seq=0
    self.capture=capture
    self.equals = equals
    self.root = Node(base=self,name=None, parent=None)

  def Path(self, name=None, path_id=None, path=None):
    if path_id:
      return self.nodes[path_id]
    elif name:
      return self.root.append(name=name)
    elif path:
      node=self.root
      for name in path:
        node=node.childs[name]
      return node
    else:
      return self.root

  def __diff(self,node,res):
    for child in node.childs.values():
      if child.is_changed_upd():
        res.append(child)
      else:
        self.__diff(child,res)

  def diff(self,node=None):
    if not node:
      node=self.root
    if node.parent and node.is_changed_upd():
      return [node]
    res=[]
    self.__diff(node,res)
    return res





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
  try:
    voidtype=value.type.target().strip_typedefs().code in (gdb.TYPE_CODE_VOID,)
  except RuntimeError:
    voidtype=False
  return   voidtype or ( #typedef T1 void; T1 *x
          value.type.strip_typedefs().code==gdb.TYPE_CODE_PTR and \
          value.type.strip_typedefs().target().strip_typedefs().code in (gdb.TYPE_CODE_STRUCT,gdb.TYPE_CODE_UNION) and \
          len(value.type.strip_typedefs().target().strip_typedefs().fields())==0)

class ValueToChunks(BasePath):
  def __init__(self, **kwargs):
    self.slice_regex=re.compile('^(-?\d+)([:, ](-?\d+))?$')
    self.user_slice={} # Данная переменная хранит информацию о том,
    # что если встречается указатель ptr, то сколько элементов указателя
    # ptr[0], ptr[1], ... нужно печатать. key=path, value=(n1,n2).
    #n1,n2 задает диапазон, включая оба конца. Если n2 есть None, то печатается строго
    #один элемент ptr[n1]
    self.expand_variable={}
    self.converters={}
    self.converters['bin_to_long'] = lambda x: long(x,2)
    self.converters['hex_to_long'] = lambda x: long(x,16)
    self.force_update={} #Если пользователь меняет значение переменной, то сюда помещается
    #path измененной переменной. Все path помещенные сюда попадут в diff между настоящим и предыдущем состоянием.
    #Смысл данной переменной в том, что если пользователь инициировал операцию изменения переменной,
    #и передал то же значение, что и было, иными словами переменная не изменится; При всяком изменении
    #у пользователя в окне появляется <Wait change: ...>. Если насильно не перерисовать переменную, то
    #Wait change так и будет висеть.
    if not hasattr(self,'subentity_name'):
      self.subentity_name = kwargs.pop('subentity_name')
    self.on_cbs={
      'expand_variable':    [],
      'collapse_variable':  [],
      'change_slice'    :   [],
      'change_variable' :   [],
    }
    capture=lambda id:(self.expand_variable.get(id), self.user_slice.get(id))
    equals=lambda old_img,old_data,new_img,new_data:  old_img==new_img and old_data==new_data
    super(ValueToChunks,self).__init__(capture=capture,equals=equals,**kwargs)


  def text_chunk(self,string,**kwargs):
    d=kwargs
    d.update({'str':string})
    return d

  def map_nodes_to_chunks(self,nodes):
    mapped=[]
    for node in nodes:
      if node.tochunks:
        func=node.tochunks
      else:
        func=self.value_to_chunks_1
      chunks=func(value=node.value(), name=str(node.name), path=node)
      assert len(chunks)==1
      mapped.append(chunks[0])
    return mapped

  @exec_main
  def diff(self,node=None):
    return self.map_nodes_to_chunks(super(ValueToChunks,self).diff(node=node))

  @exec_main
  def onclick_expand_variable(self,pkg):
    path = self.Path(path_id=pkg['path_id'])
    self.expand_variable[path.id]=True
    return self.diff(path)

  @exec_main
  def onclick_collapse_variable(self,pkg):
    path = self.Path(path_id=pkg['path_id'])
    self.expand_variable[path.id]=False
    return self.diff(path)

  @exec_main
  def onclick_change_slice(self,pkg):
    path_id=pkg['path_id']
    path=self.Path(path_id=path_id)
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
        raise mcgdbBaseException('bad input: right bound must be greater than left')
      self.user_slice[path_id] = (n1,n2)
      self.force_update[path_id]=True
    else:
      raise mcgdbBaseException('bad input: {}'.format(user_input))
    return self.diff(path)

  @exec_main
  def onclick_change_variable(self,pkg):
    #В случае некорректно введенных данных будет осуществляться обновл. переменных.
    #Поскольку после введения данных у пользователя
    #отображается <Wait change: ... >, и это сообщение надо заменить предыдущим значением.
    if not gdb_stopped():
      raise mcgdbBaseException('inferior running')
    if not inferior_alive ():
      raise mcgdbBaseException('inferior not alive')
    path_id=pkg['path_id']
    self.force_update[path_id]=True
    user_input = pkg['user_input']
    path = self.Path(path_id=path_id)
    value=path.value()
    if 'converter' in pkg:
      new_value = self.converters.get(pkg['converter'])(user_input)
    elif value.type.strip_typedefs().code in (gdb.TYPE_CODE_INT,gdb.TYPE_CODE_PTR):
      try:
        new_value=long(gdb.parse_and_eval(user_input))
      except Exception as e:
        raise mcgdbBaseException(str(e))
    else:
      new_value = user_input
    #при изменении переменной будет сгенерировано событие
    #gdb.events.memory_changed. При обработке данного события
    #должны быть обновлены переменные.
    path.assign(new_value)
    return self.map_nodes_to_chunks([path]) #Насильно перерисовываем все поддерево измененой переменной.
    #Это делается потому, что при тождественном изменение знач. переменной diff будет пустой, а в граф. окне будет <Wait change: ...>
    #который нужно заменить значением

  def base_onclick_data(self,cmdname,**kwargs):
    onclick_data = {
      'cmd' : 'onclick',
      'onclick' : cmdname,
      'subentity_dst' : self.subentity_name,
    }
    onclick_data.update(kwargs)
    return onclick_data


  def make_subarray_name(self,value,path,slice_clickable=True,**kwargs):
    if path.id not in self.user_slice:
      self.user_slice[path.id] = (0,2)
    n1,n2=self.user_slice[path.id]
    slice_kwargs={}
    slice_chunk=self.make_slice_chunk(n1,n2,path,slice_clickable=slice_clickable)
    chunks = [{'str':'*(','name':'varname'}]+\
    self.changable_value_to_chunks(value,path,**kwargs)+\
      [{'str':')','name':'varname'}]+[slice_chunk]
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

  def expand_single_array_elem(self,path):
    parent = path.parent
    return  parent!=None and self.expand_variable.get(parent.id) and \
            parent.id in self.user_slice and self.user_slice[parent.id][1]==None


  def array_to_chunks (self, value, name, n1, n2, path,
      slice_clickable=True, **kwargs):
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

    type_code=value.type.strip_typedefs().code
    if name:
      if kwargs.get('print_typename',True):
        chunks+=self.value_type_to_chunks(value,**kwargs)
        chunks.append({'str':' '})

    if type(name) is str:
      slice_chunk = self.make_slice_chunk(n1,n2,path,slice_clickable=slice_clickable)
      varname=[
        {'str':name,'name':'varname'},
        slice_chunk,
      ]
      chunks+=varname
    else:
      chunks+=name
    chunks+=[{'str':' = '}]
    try:
      if type_code==gdb.TYPE_CODE_PTR:
        value_addr = ctypes.c_ulong(long(value)).value
      else:
        value_addr = value.address
    except gdb.MemoryError:
      chunks+=self.chunks_error('accs_mem')
      return chunks

    if not self.expand_variable.get(path.id):
      chunks += self.collapsed_array_to_chunks(path,**kwargs)
      return chunks

    chunks1=[]
    array_data_chunks=[]
    n22 = n2+1 if n2!=None else n1+1
    deref_value = value[n1]
    deref_type_code = deref_value.type.strip_typedefs().code
    deref_type_str  = str(deref_value.type.strip_typedefs())
    if deref_type_code==gdb.TYPE_CODE_PTR and not re.match('.*((char \*)|(void \*))$',deref_type_str) and not is_incomplete_type_ptr(deref_value):
      elem_as_array=True
    else:
      elem_as_array=False

    arr_elem_size=deref_value.type.strip_typedefs().sizeof
    arr_size=n2-n1+1 if n2!=None else 1
    if value_addr==None or self.is_array_fetchable(value,n1,n2):
      if 'delimiter' in kwargs:
        delimiter=kwargs['delimiter']
      else:
        if deref_type_code in (gdb.TYPE_CODE_INT,gdb.TYPE_CODE_FLT):
          delimiter={'str':', '}
        else:
          delimiter={'str':',\n'}
      for i in range(n1,n22):
        value_idx = valcache(value[i])
        if elem_as_array:
          tochunks=lambda value,name,path : self.subarray_pointer_data_chunks(value,path,**kwargs)
        else:
          tochunks=lambda value,name,path : self.value_to_chunks_1(value,None,path,**kwargs)
        path_idx = path.append(
          name=i,
          tochunks=tochunks,
        )
        id=path_idx.id if elem_as_array else None
        #Если не elem_as_array, то id было добавлено в value_to_chunks_1, поэтому тут его не добавляем
        array_data_chunks__1=tochunks(value_idx,None,path_idx)
        chs = {'chunks':array_data_chunks__1}
        if id!=None: #Данное id приписывается узлу дерева в граф. окне. При помощи данного id осуществляется операция обновления дерева
          chs['id']=id
        array_data_chunks.append(chs)
        if delimiter and i!=n22-1:
          array_data_chunks.append(delimiter)
      array_data_chunks.append({'str':'\n'})
      chunks1.append({'chunks':array_data_chunks,'type_code':'TYPE_CODE_ARRAY'})
      chunks.append({
        'str':'[\n',
        'onclick_data':self.base_onclick_data('collapse_variable',path_id=path.id)
      })
      chunks.append ({
        'chunks'  : chunks1,
        'name'    : 'parenthesis',
      })
      chunks.append({
        'str':'\n]\n',
        'onclick_data':self.base_onclick_data('collapse_variable',path_id=path.id)
      })
    else:
      chunks+=self.chunks_error('accs_mem')
    return chunks

  def chunks_error(self,name):
    if name=='accs_mem':
      return [{'str':'[CantAccsMem]'}]
    else:
      assert name in ('accs_mem',)

  def subarray_pointer_data_chunks(self,value,path,**kwargs):
    '''Данная функция применяется для случая, когда обрабатывается массив указателей. value элемент такого массива.
       На выходе получается строка вида int * *(0x613ed0)[0:2] = [<Expand>],
       где значение в скобках это значение value
    '''
    name = self.make_subarray_name(value,path,**kwargs)
    chunks = [{'id':path.id,'chunks':self.pointer_data_to_chunks(value,name,path,**kwargs)}]
    return chunks

  def pointer_data_to_chunks (self,value,name,path, **kwargs):
    str_type = str(value.type.strip_typedefs())
    assert not re.match('.*void \*$',str_type)
    assert not is_incomplete_type_ptr(value)
    if  kwargs.get('disable_dereference') :
      return []
    if value.is_optimized_out:
      return self.name_to_chunks(name)+[{'str':'<OptimizedOut>'}]
    chunks=[]
    if path.id in self.user_slice:
      n1,n2 = self.user_slice.get(path.id)
    else:
      deref_type_code = value.dereference().type.strip_typedefs().code
      if deref_type_code in (gdb.TYPE_CODE_STRUCT,gdb.TYPE_CODE_UNION,gdb.TYPE_CODE_FUNC):
        n1,n2=(0,None)
      else:
        n1,n2=(0,2)
    self.user_slice[path.id] = (n1,n2)
    chunks+=self.array_to_chunks(value,name,n1,n2,path, **kwargs)
    return chunks


  def pointer_to_chunks (self, value, name, path, **kwargs):
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
          path_id=path.id,
        ),
      }]

  def stringify_type(self,type):
    ''' type есть значение value.type'''
    valuetype1 = str(type)
    valuetype2 = str(type.strip_typedefs())
    if valuetype1==valuetype2:
      valuetype=valuetype1
    else:
      valuetype='{} aka {}'.format(valuetype1,valuetype2)
    return valuetype

  def changable_value_to_chunks(self,value,path,**kwargs):
    if kwargs.get('enable_additional_text',False)==True:
      valuestr  = cached_stringify_value(value,str(path),**kwargs)
    else:
      valuestr  = stringify_value(value,**kwargs)
    if 'proposed_text' not in kwargs:
      kwargs['enable_additional_text']=False
      strvalue_pure=stringify_value(value,**kwargs)
      kwargs['proposed_text'] = strvalue_pure
    valuetype = self.stringify_type(value.type)
    return self.changable_strvalue_to_chunks(valuestr,path,valuetype,**kwargs)

  def changable_strvalue_to_chunks(self,valuestr,path,valuetype,**kwargs):
    onclick_data={
      'cmd':'onclick',
      'onclick':'change_variable',
      'path':str(path),
      'input_text': '{type} {path}'.format(path=path,type=valuetype),
      'path_id' : path.id,
      'subentity_dst' : self.subentity_name,
    }
    if 'converter' in kwargs:
      onclick_data['converter']=kwargs['converter']
    res={'str':valuestr,'name':'varvalue', 'onclick_data':onclick_data, 'onclick_user_input':True}
    if 'proposed_text' in kwargs:
      res['proposed_text']=kwargs['proposed_text']
    return [res]

  def struct_to_chunks(self,value,name,path, **kwargs):
    type_code = value.type.strip_typedefs().code
    chunks=[]
    if name:
      if kwargs.get('print_typename',True):
        chunks+=self.value_type_to_chunks(value,**kwargs)
        chunks.append({'str':' '})
      chunks+=self.name_to_chunks(name)
    #try:
    value_addr = value.address
    #except gdb.MemoryError:
    #  value_addr=None
    collapsed=self.expand_variable.get(path.id)
    expand_single = self.expand_single_array_elem(path)
    if (collapsed==False) or (collapsed==None and not expand_single):
      chunks += self.collapsed_struct_to_chunks(path, **kwargs)
      return chunks

    chunks1=[]
    data_chunks=[]
    for field in value.type.strip_typedefs().fields():
      field_name = field.name
      try:
        field_value = valcache(value[field_name])
        value_path=path.append(name=field_name)
      except gdb.error as e:
        #В C++ имеет место быть исключение вида
        #   Python Exception <class 'gdb.error'> cannot resolve overloaded method `DeviceExc': no arguments supplied:
        #while dereference this
        #Не знаю как с ними быть, поэтому вставляем текст исключения в граф. окно
        data_chunks.append({'str':str(e)+'\n'})
        continue
      data_chunks+=self.value_to_chunks_1(field_value,field_name,value_path,**kwargs)
      data_chunks.append({'str':'\n'})
    if type_code==gdb.TYPE_CODE_STRUCT:
      chunks1.append({'chunks':data_chunks,'type_code':'TYPE_CODE_STRUCT'})
    elif type_code==gdb.TYPE_CODE_UNION:
      chunks1.append({'chunks':data_chunks,'type_code':'TYPE_CODE_UNION'})
    chunks.append({
      'str':'{\n',
      'onclick_data':self.base_onclick_data('collapse_variable',path_id=path.id),
    })
    chunks.append ({
      'chunks'  : chunks1,
    })
    chunks.append({
      'str':'\n}\n',
      'onclick_data':self.base_onclick_data('collapse_variable',path_id=path.id),
    })
    return chunks



  def value_to_chunks(self,value,name,**kwargs):
    ''' Конвертирование gdb.Value в json-дерево.

        Args:
            value (gdb.Value): значение, которое нужно сконвертировать в json
            name (str): Имя, которое используется для печати NAME = VALUE. Если не задано,
                то напечатается просто VALUE.
            **print_typename (bool): True-->типы печатаются False-->не печатаются.
            **slice_clickable (bool) : Если False, то slice делается некликательным. По умолчанию True.
    '''
    assert name!=None
    path=self.Path(name=name)
    return self.value_to_chunks_1(value,name,path,**kwargs)

  def value_withstr_to_chunks(self,value,name,path,**kwargs):
    chunks=[]
    chunks+=self.name_to_chunks(name)
    chunks.append({'str':cached_stringify_value(value,str(path),enable_additional_text=True), 'name':'varvalue'})
    return chunks

  def ptrval_to_ulong(self,value):
    return ctypes.c_ulong(long(value)).value

  def functionptr_to_chunks(self,value, name, path, **kwargs):
    chunks=[]
    type_code = value.type.strip_typedefs().code
    if type_code == gdb.TYPE_CODE_METHOD:
      #Workaround: get address of class method
      s=unicode(value)
      idx=re.search('0x[0-9A-Fa-f]+',s).regs[0]
      func_addr = long(s[int(idx[0]):int(idx[1])],0)
    else:
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
    valuetype = self.stringify_type(value.type)
    chunks+=self.changable_strvalue_to_chunks(str(func_addr),path,valuetype,**kwargs)
    chunks.append({'str':' '})
    chunks.append({'str':'<{}>'.format(func_name)})
    return chunks



  def functionptr_to_chunks_argtypes(self,value, name, path, **kwargs):
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

  def value_to_chunks_1(self,value,name,path,**kwargs):
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
            **disable_dereference (bool): Если True, то dereference делаться не будет. По умолчанию False.

    '''
    chunks=[]
    type_code = value.type.strip_typedefs().code
    type_str = str(value.type.strip_typedefs())
    print_typename=kwargs.get('print_typename',True)
    if type_code in (gdb.TYPE_CODE_STRUCT,gdb.TYPE_CODE_UNION):
      chunks+=self.struct_to_chunks(value,name,path,**kwargs)
    elif type_code==gdb.TYPE_CODE_ARRAY:
      array_addr = value.address
      if array_addr!=None:
        pointer_chunks = self.pointer_to_chunks (array_addr, name, path, **kwargs)
        if len(pointer_chunks)!=0:
          chunks+=pointer_chunks
          chunks.append({'str':'\n'})
      if re.match('.*char \[.*\]$',type_str):
        chunks+=self.value_withstr_to_chunks(value,name,path,**kwargs)
      else:
        n1_orig,n2_orig = value.type.strip_typedefs().range()
        user_slice = self.user_slice.get(path.id)
        if user_slice:
          n1,n2 = user_slice
          n1 = max(n1,n1_orig)
          if n2!=None:
            n2 = min(n2,n2_orig)
        else:
          n1,n2 = n1_orig,n2_orig
        self.user_slice[path.id] = (n1,n2)
        chunks += self.array_to_chunks (value, name, n1, n2, path, **kwargs)
    elif type_code == gdb.TYPE_CODE_PTR:
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
          if value.dereference().type.strip_typedefs().code == gdb.TYPE_CODE_FUNC:
            is_funct_ptr=True
          else:
            pointer_data_chunks = self.pointer_data_to_chunks (value, name, path, **kwargs)
        if is_funct_ptr:
          pointer_chunks = self.functionptr_to_chunks(value, name, path, **kwargs)
        else:
          pointer_chunks = self.pointer_to_chunks (value, name, path, **kwargs)
        chunks+=pointer_chunks
        if len(pointer_data_chunks) > 0:
          chunks+=[{'str':'\n'}]
          chunks+=pointer_data_chunks
    elif type_code in (gdb.TYPE_CODE_METHOD,):
      chunks += self.functionptr_to_chunks(value, name, path, **kwargs)
    else:
      if  name!=None:
        if print_typename:
          chunks+=self.value_type_to_chunks(value,**kwargs)
        chunks.append({'str':' '})
        chunks+=self.name_to_chunks(name)
      chunks+=self.changable_value_to_chunks(value,path,**kwargs)
    res_chunk={'chunks':chunks, 'id':path.id}
    return [res_chunk]

  def make_slice_chunk(self,n1,n2,path,slice_clickable=True):
    chunks=[]
    if n2==None:
      chunks.append({'str':'[{idx}]'.format(idx=n1), 'name':'slice'})
    else:
      chunks.append({'str':'[{idx1}:{idx2}]'.format(idx1=n1,idx2=n2), 'name':'slice'})
    slice_chunk={
      'chunks':chunks,
    }

    if slice_clickable:
      onclick_data={
        'cmd':'onclick',
        'onclick':'change_slice',
        'input_text':'enter new slice N or N:M',
        'path_id' : path.id,
        'subentity_dst' : self.subentity_name,
      }
      slice_chunk['onclick_data']=onclick_data
      slice_chunk['onclick_user_input']=True

    return slice_chunk

  def integer_as_struct_chunks(self,value,name,**kwargs):
    assert name!=None
    path = self.Path(name)
    return self.integer_as_struct_chunks_1(value,name,path,**kwargs)

  def integer_as_struct_chunks_1(self,value,name,path,**kwargs):
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
    data_chunks += self.changable_value_to_chunks(value,path,integer_mode='dec',index_name=str(path)+'_dec')
    data_chunks += [{'str':'\n'}]
    data_chunks += self.name_to_chunks('hex')
    data_chunks += self.changable_value_to_chunks(value,path,integer_mode='hex',converter='hex_to_long',index_name=str(path)+'_hex')
    data_chunks += [{'str':'\n'}]
    data_chunks += self.name_to_chunks('bin')
    data_chunks += self.changable_value_to_chunks(value,path,integer_mode='bin',converter='bin_to_long',index_name=str(path)+'_bin')
    data_chunks += [{'str':'\n'}]
    data_chunks += [{'str':'\n'}]
    chunks.append({'str':'{\n',})
    chunks+=[{'chunks':data_chunks,'type_code':'TYPE_CODE_STRUCT'}]
    chunks.append({'str':'}\n',})
    return [{'chunks':chunks, 'id':path.id}]

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





