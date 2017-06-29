#coding=utf8

import gdb

import mcgdb.basewin
from mcgdb.common import exec_main, gdb_print
from mcgdb.basewin import BaseWin, TABID_TMP
from mcgdb.valuetochunks import ValueToChunks

import re

class AsmWin(BaseWin,ValueToChunks):
  '''Окно для отображение ассемблерного кода.
  '''

  type='asmwin'
  startcmd='mcgdb open asm'

  @exec_main
  def __init__(self,**kwargs):
    super(AsmWin,self).__init__(**kwargs)
    self.location=kwargs.get('location') #display only this function.
    self.start_addr=None
    self.end_addr=None
    self.pc=None
    self.selected_asm_op_id=None
    self.current_display_blocks=None
    self.need_redisplay_asm=True
    self.reg_disas_line_addr = re.compile('(=>)?\s+(0x[0-9a-fA-F]+)')
    self.reg_find_addr = re.compile('\s0x[0-9a-fA-F]+\s')
    self.addr_to_row=None
    self.cur_displayed_succ = False #данный флаг имеет значение True тогда и только тогда,
    #когда asm для текущей позиции исполнения был успешно отправлен на отрисовку. Данный флаг
    #используется для определения того, нужно ли уставить/убирать текущую позицию исполнения
    #в граф. окне.

  def onclick_breakpoint(self,pkg): pass

  @exec_main
  def get_selected_frame_pc(self):
    frame = gdb.selected_frame ()
    if not frame:
      return None
    return frame.pc()

  @exec_main
  def get_function_block(self,frame):
    block=frame.block()
    while block:
      if block.function:
        return block
      block=block.superblock

  @exec_main
  def get_selected_frame_func(self):
    try:
      frame = gdb.selected_frame ()
    except gdb.error:
      return None,None,None
    if not frame:
      return None,None,None
    try:
      block = self.get_function_block(frame)
      if block:
        start_addr,end_addr = block.start,block.end
      else:
        start_addr,end_addr = None,None
      return (frame.name(),start_addr,end_addr)
    except RuntimeError:
      #for ex., if current frame corresponding
      #to malloc function, then selected_frame().block()
      #throw RuntimeError
      pc=frame.pc()
      res=gdb.execute('maintenance translate-address {addr}'.format(addr=pc),False,True)
      name = res.split()[0] #function name
      res=gdb.execute('disas',False,True)
      lines=res.split('\n')
      first=lines[1]
      last=lines[-3]
      start_addr = long(self.reg_disas_line_addr.search(first).groups()[1],0)
      end_addr = long(self.reg_disas_line_addr.search(last).groups()[1],0)
      return name,start_addr,end_addr

  @exec_main
  def get_func_addr_by_location(self,location):
    try:
      dl=gdb.decode_line(self.location)
    except gdb.error as err:
      return (None,None)
    if dl[0]!=None:
      return (None,None)
    sal=dl[1][0]
    start_addr,end_addr = sal.pc,sal.last
    return start_addr,end_addr


  def process_connection(self):
    rc=super(AsmWin,self).process_connection()
    if rc:
      self.update_asm_code()
    return rc

  def tablemsg_rows(self,msg):
    col={'chunks':[self.text_chunk(msg)]}
    row={'columns':[col]}
    rows=[row]
    return rows


  def tablemsg(self,msg):
    rows=self.tablemsg_rows(msg)
    table = {'rows':rows}
    self.selected_asm_op_id=None
    return {'cmd':'exemplar_create','table_name':'asm','id':TABID_TMP,'table':table,'set':True,}

  def send_tablemsg(self,msg):
    self.send(self.tablemsg(msg))

#  def asm_to_chunks(self):
#    try:
#      return self.asm_to_chunks_1()
#    except gdb.error as e:
#      self.selected_asm_op_id = None
#      return self.tablemsg_rows(str(e)),-1

  @exec_main
  def asm_to_chunks(self):
    if self.location:
      #try:
      #  dl=gdb.decode_line(self.location)
      #except gdb.error as err:
      #  return self.text_chunk(str(err))
      #if dl[0]!=None:
      #  return self.text_chunk(dl[0])
      #sal=dl[1][0]
      #start_addr,end_addr = sal.pc,sal.last
      pass
    else:
      _,start_addr,end_addr = self.get_selected_frame_func()
    assert start_addr!=None
    assert end_addr!=None
    frame = gdb.selected_frame()
    if frame==None:
      return self.text_chunk('you must select thread')
    arch = frame.architecture()
    disas = arch.disassemble(start_addr,end_addr)
    rows=[]
    pc=frame.pc()
    selected_row=None
    self.addr_to_row={}
    for idx,row in enumerate(disas):
      asm=row['asm'].split()
      cmd=asm[0]
      code=' '.join(asm[1:])
      addr=row['addr']
      spaces=' '*(10-len(cmd))
      kw={'id':addr}
      if addr==pc:
        kw['selected']=True
        selected_row=idx
        self.selected_asm_op_id = addr
      self.addr_to_row[addr]=idx
      cols={'columns':[
        {'chunks':[
          self.text_chunk('0x{:016x}'.format(addr)),
          self.text_chunk(spaces),
          self.text_chunk(cmd,name='asm_op', **kw),
          self.text_chunk('  '),
          self.text_chunk(code),
        ]},
      ]}
      rows.append(cols)
    return rows,selected_row

  @exec_main
  def update_asm_code(self):
    try:
      funcname,start_addr,end_addr = self.get_selected_frame_func()
    except gdb.error as e:
      self.unselect_asm_op()
      pkg=self.tablemsg(str(e))
      self.send(pkg)
      self.cur_displayed_succ=False
      self.start_addr=None
      self.end_addr=None
      return
    try:
      frame=gdb.selected_frame()
    except gdb.error:
      frame=None
    need_update_current_op=frame and self.pc!=frame.pc()
    if self.location:
      need_update_asm_code=self.need_redisplay_asm
    else:
      need_update_asm_code=self.need_redisplay_asm or self.start_addr!=start_addr or self.end_addr!=end_addr
    if need_update_asm_code:
      self.need_redisplay_asm=False
      selected_row=None
      id,data=self.id_get((start_addr,end_addr))
      if id==None:
        self.cur_displayed_succ=False
        self.unselect_asm_op() #убираем красную линию
        #текущая функция ранее не отрисовывалась. Необходимо создать новый экземпляр таблицы
        if not frame:
          pkg=self.tablemsg('not frame selected')
          self.send(pkg)
          self.selected_asm_op_id=None
        else:
          #генерация таблицы с asm-кодом текущей функции
          try:
            asm_rows,selected_row = self.asm_to_chunks()
            id=self.id_insert((start_addr,end_addr),{'addr_to_row':self.addr_to_row})
            table={'rows':asm_rows, 'draw_vline':False, 'draw_hline':False}
            if selected_row!=None:
              table['selected_row']=selected_row
            pkg={'cmd':'exemplar_create','table_name':'asm','id':id,'table':table,'set':True}
            self.send(pkg)
            self.cur_displayed_succ=True
          except gdb.error as e:
            self.selected_asm_op_id = None
            pkg=self.tablemsg(str(e))
            self.send(pkg)
      else:
        #экземпляр таблицы был отрисова ранее.
        #убираем отметку с текущего экземпляра и загружаем ранее отрисовывавшийся
        self.unselect_asm_op()
        self.addr_to_row = data['addr_to_row']
        self.exemplar_set(id,'asm')
        self.cur_displayed_succ=True
        self.select_asm_op()
    elif need_update_current_op:
      self.update_asm_op()
    self.start_addr=start_addr
    self.end_addr=end_addr
    if self.cur_displayed_succ:
      assert self.selected_asm_op_id==frame.pc()
    if frame:
      self.pc=frame.pc()
    else:
      self.pc=None

  def select_asm_op(self):
    if not self.cur_displayed_succ:
      return
    try:
      frame = gdb.selected_frame()
      pc=frame.pc()
      self.select_node('asm',pc,True)
      self.selected_asm_op_id=pc
      self.do_row_visible(self.addr_to_row[pc])
    except gdb.error:
      pass

  def unselect_asm_op(self):
    if self.selected_asm_op_id!=None:
      self.select_node('asm',self.selected_asm_op_id,False)
      self.selected_asm_op_id=None

  def update_asm_op(self):
    if not self.cur_displayed_succ:
      return
    data=[]
    if self.selected_asm_op_id:
      data.append({'id':self.selected_asm_op_id,'selected':False})
      self.selected_asm_op_id=None
    pc=None
    try:
      frame = gdb.selected_frame()
      pc=frame.pc()
      data.append({'id':pc,'selected':True,'visible':True})
      self.selected_asm_op_id=pc
    except gdb.error:
      pass
    if data:
      pkg={'cmd':'update_nodes', 'table_name':'asm', 'nodes':data}
      self.send(pkg)

  def gdbevt_exited(self,evt):
    self.send_tablemsg(u'target program exited')

  def gdbevt_stop(self,evt):
    self.update_asm_code()

  def gdbevt_new_objfile(self,evt):
    self.need_redisplay_asm=True
    self.update_asm_code()

  def shellcmd_up(self,pkg):
    self.update_asm_code()

  def shellcmd_down(self,pkg):
    self.update_asm_code()

  def shellcmd_thread(self,pkg):
    self.update_asm_code()

  def mcgdbevt_frame(self,data):
    return self.update_asm_code()


