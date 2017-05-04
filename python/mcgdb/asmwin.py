#coding=utf8

import gdb

import mcgdb.basewin
from mcgdb.common import exec_main

import re

class AsmWin(mcgdb.basewin.BaseWin):
  '''Окно для отображение ассемблерного кода.
  '''

  type='asmwin'
  startcmd='mcgdb open asm'

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
    self.click_cmd_cbs={
      'breakpoint_insert' : self.click_breakpoint_insert,
      'breakpoint_remove' : self.click_breakpoint_remove,
    }

  def click_breakpoint_insert(self,pkg): pass
  def click_breakpoint_remove(self,pkg): pass

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
    for idx,row in enumerate(disas):
      asm=row['asm'].split()
      cmd=asm[0]
      code=' '.join(asm[1:])
      addr=row['addr']
      spaces=' '*(10-len(cmd))
      kw={}
      if addr==pc:
        kw['selected']=True
        selected_row=idx
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
      pkg={'cmd':'table_asm','table':self.tablemsg(str(e))}
      self.send(pkg)
      return
    #funcname_loc,start_addr_loc,end_addr_loc = self.get_func_addr_by_location(self.location)
    try:
      frame=gdb.selected_frame()
    except gdb.error:
      frame=None
    need_update_cur_pos=frame and self.pc!=frame.pc
    if self.location:
      need_update_asm_code=self.need_redisplay_asm
    else:
      need_update_asm_code=self.need_redisplay_asm or self.start_addr!=start_addr or self.end_addr!=end_addr
    if need_update_asm_code:
      selected_row=None
      if not frame:
        asm_rows = self.text_chunk('not frame selected')
      else:
        asm_rows,selected_row = self.asm_to_chunks()
      table={'rows':asm_rows, 'draw_vline':False, 'draw_hline':False}
      if selected_row!=None:
        table['selected_row']=selected_row
      pkg={'cmd':'table_asm','table':table,}
      self.send(pkg)
    if need_update_cur_pos:
      pass

  def gdbevt_stop(self,evt):
    self.update_asm_code()

  def gdbevt_new_objfile(self,evt):
    self.need_redisplay_asm=True
    self.update_asm_code()

  def shellcmd_frame_up(self):
    self.update_asm_code()

  def shellcmd_frame_down(self):
    self.update_asm_code()

  def shellcmd_frame(self):
    self.update_asm_code()

  def shellcmd_thread(self):
    self.update_asm_code()

