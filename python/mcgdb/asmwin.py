#coding=utf8

import gdb

import mcgdb.basewin
from mcgdb.common import exec_main, gdb_print, INDEX, TABID_TMP, FrmaeNotSelected, gdbprint
from mcgdb.basewin import BaseWin, TablePackages
from mcgdb.valuetochunks import ValueToChunks
from mcgdb.auxwin import ValuesExemplar, SubentityUpdate

import re

class AsmCommon(object):
  @exec_main
  def __init__(self,*args,**kwargs):
    super(AsmCommon,self).__init__(*args,**kwargs)
    self.reg_disas_line_addr = re.compile('(=>)?\s+(0x[0-9a-fA-F]+)')
    self.selected_asm_op_id=None

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



class CurrentAsm(ValuesExemplar,AsmCommon,ValueToChunks,TablePackages):
  def __init__(self,*args,**kwargs):
    super(CurrentAsm,self).__init__(*args,**kwargs)
    self.addr_to_row={}

  def get_table(self):
    try:
      return self.asm_to_chunks()
    except FrmaeNotSelected:
      return self.one_row_one_cell('No frame selected')

  def need_update(self):
    return self.pkgs_update_asm_op()

  @exec_main
  def asm_to_chunks(self):
    frame = gdb.selected_frame()
    if frame==None:
      raise FrmaeNotSelected
    _,start_addr,end_addr = self.get_selected_frame_func()
    assert start_addr!=None
    assert end_addr!=None
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
      kw={'id':addr}
      if addr==pc:
        kw['selected']=True
        selected_row=idx
        self.selected_asm_op_id = addr
      self.addr_to_row[addr]=idx
      cols={'columns':[
        {'chunks':[
          self.text_chunk('0x{addr:016x}{spaces}'.format(addr=addr,spaces=spaces)),
          self.text_chunk(cmd,name='asm_op', **kw),
          self.text_chunk('  {}'.format(code)),
        ]},
      ]}
      rows.append(cols)
    return {'rows':rows, 'draw_vline':False, 'draw_hline':False}



  def pkg_select_asm_op(self):
    pkg=None
    try:
      frame = gdb.selected_frame()
      pc=frame.pc()
      pkg = self.pkg_select_node(id=pc,selected=True,visible=True)
      self.selected_asm_op_id=pc
    except gdb.error:
      pass
    return pkg

  def pkg_unselect_asm_op(self):
    if self.selected_asm_op_id!=None:
      pkg=self.pkg_select_node(self.selected_asm_op_id,False)
      self.selected_asm_op_id=None
      return pkg

  def pkgs_update_asm_op(self):
    pkgs=[]
    if self.selected_asm_op_id:
      pkgs.append(self.pkg_select_node(id=self.selected_asm_op_id,selected=False))
      self.selected_asm_op_id=None
    pc=None
    try:
      frame = gdb.selected_frame()
      pc=frame.pc()
      pkgs.append(self.pkg_select_node(id=pc,selected=True,visible=True))
      self.selected_asm_op_id=pc
    except gdb.error:
      pass
    return pkgs


class AsmTable(SubentityUpdate,AsmCommon):
  subentity_name='asm'
  values_class = CurrentAsm

  @exec_main
  def get_key(self):
    _,start_addr,end_addr = self.get_selected_frame_func()
    return (start_addr,end_addr)


class AsmWin(BaseWin):
  '''Окно для отображение ассемблерного кода.'''

  type='asmwin'
  startcmd='mcgdb open asm'
  subentities_cls=[AsmTable]




