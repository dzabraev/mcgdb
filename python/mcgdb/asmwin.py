#coding=utf8

import gdb

import mcgdb.basewin
from mcgdb.common import exec_main, gdb_print, INDEX, TABID_TMP, FrmaeNotSelected, gdbprint, frame_func_addr
from mcgdb.basewin import BaseWin, TablePackages
from mcgdb.valuetochunks import ValueToChunks
from mcgdb.auxwin import ValuesExemplar, SubentityUpdate

import re




class CurrentAsm(ValuesExemplar,ValueToChunks,TablePackages):
  def __init__(self,*args,**kwargs):
    super(CurrentAsm,self).__init__(*args,**kwargs)
    self.addr_to_row={}
    self.selected_asm_op_id=None

  def get_table(self):
    try:
      return self.asm_to_chunks()
    except FrmaeNotSelected:
      return self.one_row_one_cell('No frame selected')

  def need_update(self):
    return self.pkgs_update_asm_op()

  def asm_to_chunks(self):
    frame = gdb.selected_frame()
    if frame==None:
      raise FrmaeNotSelected
    _,start_addr,end_addr = frame_func_addr(frame)
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


class AsmTable(SubentityUpdate):
  subentity_name='asm'
  values_class = CurrentAsm

  def get_key(self):
    frame = gdb.selected_frame()
    _,start_addr,end_addr = frame_func_addr(frame)
    return (start_addr,end_addr)


class AsmWin(BaseWin):
  '''Окно для отображение ассемблерного кода.'''

  type='asmwin'
  startcmd='mcgdb open asm'
  subentities_cls=[AsmTable]




