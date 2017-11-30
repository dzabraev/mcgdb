#coding=utf8

import gdb
import os,stat

from mcgdb.basewin import BaseWin
from mcgdb.common import gdb_print, exec_main, gdbprint, bpModif, get_bp_locations

class SrcWin(BaseWin):

  type='srcwin'
  startcmd='mcgdb open src'
  subentities_cls=[]


  def __init__(self, **kwargs):
    super(SrcWin,self).__init__(**kwargs)
    self.exec_filename=None #текущему фрейму соответствует это имя файла с исходным кодом.
    self.exec_line=None     #номер строки текущей позиции исполнения программы
    self.exec_filename_opened=False
    self.notexistsmsg_showing=False
    self.bp_gdb_mc={} #map breakpoint id. gdb_bp_id --> mcedit_bp_id
    self.bpid_without_extid=set()

  def process_connection(self):
    rc=super(SrcWin,self).process_connection()
    if rc:
      self.update_current_frame()
      self.send_pkg_update_threads()
      self.update_breakpoints()
    return rc

  def gdbevt_exited(self,pkg):
    self.update_current_frame()

  def gdbevt_stop(self,pkg):
    self.update_current_frame()
    #self.update_breakpoints()

  def gdbevt_new_objfile(self,pkg):
    self.update_current_frame()

  def gdbevt_clear_objfiles(self,pkg):
    self.update_current_frame()

  def gdbevt_breakpoint_created(self,pkg):
    bp, = pkg['evt']
    self.send(self.pkg_update_bps([bp]))

  def gdbevt_breakpoint_modified(self,pkg):
    bp, = pkg['evt']
    resp=self.pkg_update_bps([bp])
    if resp is not None:
      self.send(resp)

  def gdbevt_breakpoint_deleted(self,pkg):
    bp, = pkg['evt']
    resp=self.pkg_delete_bps([bp])
    if resp is not None:
      self.send(resp)


  def shellcmd_up(self,pkg):
    self.update_current_frame()

  def shellcmd_down(self,pkg):
    self.update_current_frame()

  def mcgdbevt_frame(self,pkg):
    self.update_current_frame()

  def shellcmd_thread(self,pkg):
    self.update_current_frame()
    self.send_pkg_update_threads()

  def mcgdbevt_thread(self,pkg):
    self.update_current_frame()
    self.send_pkg_update_threads()

  def pkg_delete_bps(self,bps):
    valid_numbers=set([bp.number for bp in gdb.breakpoints() if bp.is_valid()])
    stored_numbers=set(self.bp_gdb_mc.keys())
    invalid_numbers=stored_numbers - valid_numbers
    ids=[]
    for number in invalid_numbers:
      bp_data={}
      bp_data['number']=number
      external_id = self.bp_gdb_mc[number]
      if external_id is not None:
        bp_data['external_id']=external_id
      ids.append(bp_data)
      del self.bp_gdb_mc[number]
    for bp in bps:
      if not bp.is_valid():
        continue
      number=bp.number
      if number in self.bp_gdb_mc:
        bp_data={}
        bp_data['number']=number
        external_id = self.bp_gdb_mc[number]
        if external_id is not None:
          bp_data['external_id']=external_id
        ids.append(bp_data)
    if len(ids)==0:
      return
    return {
      'cmd':'bpsdel',
      'ids':ids,
    }

  def pkg_update_bps(self,bps):
    bps_data=[]
    for bp in bps:
      if not bp.is_valid() or not bp.visible or bp.type!=gdb.BP_BREAKPOINT:
        continue
      bp_data={}
      for name in ['silent','thread','ignore_count','number','temporary','hit_count','condition','commands','enabled']:
        value = getattr(bp,name)
        bp_data[name]=value
      external_id = self.bp_gdb_mc.get(bp.number)
      if external_id is not None:
        bp_data['external_id']=external_id
      else:
        self.bp_gdb_mc[bp.number] = None
        bp_data['locations'] = map(lambda fl:{'filename':fl[0],'line':fl[1]},get_bp_locations(bp))
      bps_data.append(bp_data)

    if len(bps_data)==0:
      return
    sel_th = gdb.selected_thread()
    return {
      'cmd':'bpsupd',
      'bps_data':bps_data,
    }

  def update_breakpoints(self):
    self.send(self.pkg_update_bps(gdb.breakpoints()))

  #commands from editor
  def onclick_breakpoints(self,pkg):
    delete_now=[]
    for bp_data in pkg.get('delete',[]):
      external_id=bp_data['external_id']
      number = bpModif.delete( win_id=id(self),
                      external_id=external_id,
                      number=bp_data.get('number'))
      if number is not None:
        self.bp_gdb_mc[number] = external_id
      else:
        #breakpoint creation request made, but breakpoint didn't create.
        #i.e. we receive cancelation of bp creation
        delete_now.append({
          'number':number,
          'external_id':external_id,
        })
    if len(delete_now)>0:
      self.send({'cmd':'bpsdel','ids':delete_now}) #just send delete confirmation
    for bp_data in pkg.get('update',[]):
      #cration or modification
      kwargs={name:bp_data.get(name) for name in [
        'enabled','silent','ignore_count','temporary','thread',
        'condition','commands','external_id','number','create_loc'
      ]}
      external_id = bp_data['external_id']
      assert external_id is not None
      number = bp_data.get('number')
      if number is not None and external_id not in self.bp_gdb_mc:
        self.bp_gdb_mc[number] = external_id
      kwargs['after_create']= (lambda external_id : lambda bp: self.bp_gdb_mc.update({bp.number:external_id}))(external_id)
      bpModif.update(win_id=id(self),**kwargs)



  def can_open_file(self,filename):
    return os.path.exists(filename) and \
           os.stat(filename).st_mode & stat.S_IFREG and \
           os.stat(filename).st_mode & stat.S_IREAD

  def close_in_window(self):
    if self.exec_filename_opened:
      self.send({'cmd':'fclose'})
      self.exec_filename_opened=False
    elif self.notexistsmsg_showing:
      self.send({'cmd':'fclose'})
      self.notexistsmsg_showing=False

  @exec_main
  def update_current_frame(self):
    '''Данная функция извлекает из gdb текущий файл
        и номер строки исполнения. После чего, если необходимо, открывает
        файл с исходником в редакторе и перемещает экран к линии исполнения.
    '''
    filename,line = self.get_current_position()
    can_open = filename and self.can_open_file(filename)
    if not can_open:
      if not self.notexistsmsg_showing:
        self.close_in_window()
        self.send({'cmd':'fopen'})
        self.send({'cmd':'insert_str','msg':"Current execution position or source file is unknown.\nOr file can't be open."})
        self.notexistsmsg_showing=True
    else:
      if filename!=self.exec_filename or not self.exec_filename_opened:
        #execution file changed. New file can be opening.
        self.close_in_window()
        self.send({
          'cmd'       :   'fopen',
          'filename'  :   filename,
          'line'      :   line if line!=None else 0,
        })
        self.send({'cmd':'set_curline',  'line':line})
        self.exec_filename_opened=True
      elif filename==self.exec_filename and line!=self.exec_line and line!=None:
        assert self.exec_filename_opened==True
        self.send({'cmd':'set_curline',  'line':line})
        self.exec_line=line
    self.exec_filename=filename
    self.exec_line=line


  def set_color(self,pkg):
    self.send(pkg)

  def terminate(self):
    pass


