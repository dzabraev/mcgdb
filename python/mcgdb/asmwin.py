#coding=utf8

import gdb

import mcgdb.basewin
from mcgdb.common import exec_main, gdb_print, INDEX, TABID_TMP, FrmaeNotSelected, gdbprint, frame_func_addr
from mcgdb.basewin import BaseWin, TablePackages
from mcgdb.valuetochunks import ValueToChunks
from mcgdb.auxwin import ValuesExemplar, SubentityUpdate, KeyNotAvailable

import re




class CurrentAsm(ValuesExemplar,ValueToChunks,TablePackages):
  def __init__(self,*args,**kwargs):
    super(CurrentAsm,self).__init__(*args,**kwargs)
    self.addr_to_row={}
    self.addr_id={}
    self.addr_id_cnt=1
    self.selected_asm_op_id=None
    self.asm_drawn=False

  def get_addr_id(self,addr):
    #отображаем адреса на отрезок натурального ряда, поскольку размер адреса
    #и размер целого числа в граф. окне могут различаться. Такое может произойти при
    #отладке программы с не нативной архитектурой
    if addr in self.addr_id:
      return self.addr_id[addr]
    else:
      tmp=self.addr_id_cnt
      self.addr_id[addr] = self.addr_id_cnt
      self.addr_id_cnt+=1
      return tmp

  def get_table(self):
    try:
      return self.asm_to_chunks()
    except FrmaeNotSelected:
      self.asm_drawn=False
      return self.one_row_one_cell('No frame selected')

  def need_update(self):
    return self.pkgs_update_asm_op()

  def asm_to_chunks(self):
    frame = gdb.selected_frame()
    if frame==None:
      raise FrmaeNotSelected
    _,start_addr,end_addr = frame_func_addr(frame)
    if start_addr==None or end_addr==None:
      self.asm_drawn=False
      return self.one_row_one_cell("can't locate start and stop adresses of function")
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
      kw={'id':self.get_addr_id(addr)}
      if addr==pc:
        kw['selected']=True
        kw['visible']=True
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
    self.asm_drawn=True
    return {'rows':rows, 'draw_vline':False, 'draw_hline':False}



  def pkg_select_asm_op(self):
    assert self.asm_drawn
    pkg=None
    try:
      frame = gdb.selected_frame()
      pc=frame.pc()
      pkg = self.pkg_select_node(id=self.get_addr_id(pc),selected=True,visible=True)
      self.selected_asm_op_id=pc
    except gdb.error:
      pass
    return pkg

  def pkg_unselect_asm_op(self):
    assert self.asm_drawn
    if self.selected_asm_op_id!=None:
      id=self.get_addr_id(self.selected_asm_op_id)
      pkg=self.pkg_select_node(id,False)
      self.selected_asm_op_id=None
      return pkg

  def pkgs_update_asm_op(self):
    pkgs=[]
    if not self.asm_drawn:
      return []
    if self.selected_asm_op_id:
      id=self.get_addr_id(self.selected_asm_op_id)
      pkgs.append(self.pkg_select_node(id=id,selected=False))
      self.selected_asm_op_id=None
    pc=None
    try:
      frame = gdb.selected_frame()
      pc=frame.pc()
      id=self.get_addr_id(pc)
      pkgs.append(self.pkg_select_node(id=id,selected=True,visible=True))
      self.selected_asm_op_id=pc
    except gdb.error:
      pass
    return pkgs


class AsmTable(SubentityUpdate):
  subentity_name='asm'
  values_class = CurrentAsm

  def get_key(self):
    try:
      frame = gdb.selected_frame()
    except gdb.error:
      raise KeyNotAvailable
    _,start_addr,end_addr = frame_func_addr(frame)
    return (start_addr,end_addr)


class AsmWin(BaseWin):
  '''Окно для отображение ассемблерного кода.'''

  type='asmwin'
  startcmd='mcgdb open asm'
  subentities_cls=[AsmTable]




