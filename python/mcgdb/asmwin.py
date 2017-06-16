#coding=utf8

import gdb

import mcgdb.basewin
from mcgdb.common import exec_main
from mcgdb.basewin import BaseWin
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
    self.current_display_blocks=None
    self.need_redisplay_asm=True
    self.reg_disas_line_addr = re.compile('(=>)?\s+(0x[0-9a-fA-F]+)')
    self.reg_find_addr = re.compile('\s0x[0-9a-fA-F]+\s')

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

  def tablemsg(self,msg):
    return [{'columns':[
          { 'chunks':[self.text_chunk(msg)] }
        ]}]


  def asm_to_chunks(self):
    try:
      return self.asm_to_chunks_1()
    except gdb.error as e:
      self.selected_asm_op_id = None
      return self.tablemsg(str(e)),-1

  @exec_main
  def asm_to_chunks_1(self):
    if self.location:
      try:
        dl=gdb.decode_line(self.location)
      except gdb.error as err:
        return self.text_chunk(str(err))
      if dl[0]!=None:
        return self.text_chunk(dl[0])
      sal=dl[1][0]
      start_addr,end_addr = sal.pc,sal.last
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
      pkg={'cmd':'exemplar_create','table_name':'asm','table':self.tablemsg(str(e))}
      self.send(pkg)
      return
    #funcname_loc,start_addr_loc,end_addr_loc = self.get_func_addr_by_location(self.location)
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
      if not frame:
        asm_rows = self.text_chunk('not frame selected')
      else:
        asm_rows,selected_row = self.asm_to_chunks()
      table={'rows':asm_rows, 'draw_vline':False, 'draw_hline':False}
      if selected_row!=None:
        table['selected_row']=selected_row
      pkg={'cmd':'exemplar_create','table_name':'asm','table':table,}
      self.send(pkg)
    elif need_update_current_op:
      if self.selected_asm_op_id!=None:
        node_data={'id':self.selected_asm_op_id,'selected':False}
        pkg={'cmd':'update_node','table_name':'asm', 'node_data':node_data}
        self.send(pkg)
      self.selected_asm_op_id = frame.pc()
      node_data={'id':frame.pc(),'selected':True}
      pkg={'cmd':'update_node','table_name':'asm', 'node_data':node_data}
      self.send(pkg)
      pkg={'cmd':'do_row_visible','table_name':'asm', 'nrow':self.addr_to_row[self.selected_asm_op_id]}
      self.send(pkg)
    self.start_addr=start_addr
    self.end_addr=end_addr
    if frame:
      self.pc=frame.pc()
    else:
      self.pc=None

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


