#coding=utf8

import gdb
import os,stat

from mcgdb.basewin import BaseWin
from mcgdb.common import breakpoint_queue
from mcgdb.common import gdb_print, exec_main, gdbprint

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

  def process_connection(self):
    rc=super(SrcWin,self).process_connection()
    if rc:
      self.update_current_frame()
      self.update_breakpoints()
    return rc

  def gdbevt_exited(self,pkg):
    self.update_current_frame()

  def gdbevt_stop(self,pkg):
    self.update_current_frame()
    self.update_breakpoints()

  def gdbevt_new_objfile(self,pkg):
    self.update_current_frame()

  def gdbevt_clear_objfiles(self,pkg):
    self.update_current_frame()

  def gdbevt_breakpoint_created(self,pkg):
    self.update_breakpoints()

  def gdbevt_breakpoint_modified(self,pkg):
    self.update_breakpoints()

  def gdbevt_breakpoint_deleted(self,pkg):
    self.update_breakpoints()


  def shellcmd_up(self,pkg):
    self.update_current_frame()
    self.update_breakpoints()

  def shellcmd_down(self,pkg):
    self.update_current_frame()
    self.update_breakpoints()

  def mcgdbevt_frame(self,pkg):
    self.update_current_frame()
    self.update_breakpoints()

  def shellcmd_thread(self,pkg):
    self.update_current_frame()
    self.update_breakpoints()

  def mcgdbevt_thread(self,pkg):
    self.update_current_frame()
    self.update_breakpoints()

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
        self.send({'cmd':'bpmark','bpmark':False})
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
        self.send({'cmd':'bpmark','bpmark':True})
        self.send({'cmd':'set_curline',  'line':line})
        self.exec_filename_opened=True
      elif filename==self.exec_filename and line!=self.exec_line and line!=None:
        assert self.exec_filename_opened==True
        self.send({'cmd':'set_curline',  'line':line})
        self.exec_line=line
    self.exec_filename=filename
    self.exec_line=line



  def update_breakpoints(self):
    if not self.exec_filename_opened:
      return
    normal=breakpoint_queue.get_bps_locs_normal(self.exec_filename)
    disabled=breakpoint_queue.get_bps_locs_disabled(self.exec_filename)
    wait_remove=breakpoint_queue.get_bps_locs_wait_remove(self.exec_filename)
    wait_insert=breakpoint_queue.get_bps_locs_wait_insert(self.exec_filename)
    pkg={
      'cmd':'breakpoints',
      'normal'          :   normal,
      'wait_insert'     :   wait_insert,
      'wait_remove'     :   wait_remove,
      'disabled'        :   disabled,
      'remove'          :   [],
      'clear':True,
    }
    self.send(pkg)

  #commands from editor
  def onclick_breakpoint(self,pkg):
    action = pkg['action']
    if action in ('insert','update'):
      self.breakpoint_insert(
        filename  =   pkg['filename'],
        line      =   pkg['line'],
        condition =   pkg.get('condition','')
        disabled  =   pkg['disabled']
      )
    elif action=="delete":
      self.breakpoint_delete(
        filename  =   pkg['filename'],
        line      =   pkg['line'],
      )

    line=pkg['line']
    breakpoint_queue.insert_or_delete(self.exec_filename,line)
    breakpoint_queue.process()
    return [{'cmd':'check_breakpoint'}]


  def __bp_delete_pending(self,filename,line):
    key=(filename,line)
    if key in self.__bps_insert:
      def self.__bps_insert[key]
    else:
      self.__bps_delete.add(key)

  def __bp_delete(self,filename,line):
    bp=self.find_bp_in_gdb(filename,line)
    bp.delete()
    self.notify_bp_deleted(filename,line)
    return [{'cmd':'check_breakpoint'}]

  def __bp_insert_pending(self,filename,line,condition,disabled):
    key=(filename,line)
    if key in self.__bps_delete:
      self.__bps_delete.remove(key)
    self.__bps_insert[key]={
      'filename':filename,
      'line':line,
      'condition':condition,
      'disabled':disabled,
    }

  def __bp_insert(self,filename,line,condition,disabled):
    bp=gdb.Breakpoint('{}:{}'.format(filename,line))
    if condition:
      bp.condition=condition
    bp.disabled=disabled
    self.notify_bp_inserted(filename,line)
    return [{'cmd':'check_breakpoint'}]

  def __process_brekpoints(self):
    for filename,line in self.__bps_delete:
      bp=self.find_bp_in_gdb(filename,line)
      bp.delete()
      self.notify_bp_deleted(filename,line)


  def breakpoint_insert(self,filename,line,condition,disabled):
    return if_gdbstopped_else(
      stopped=lambda : self.__bp_insert(filename,line,condition,disabled),
      running=lambda : self.__bp_insert_pending(filename,line,condition,disabled),
    )

  def breakpoint_delete(self,filename,line):
    return if_gdbstopped_else(
      stopped=lambda : self.__bp_delete(filename,line),
      running=lambda : self.__bp_delete_pending(filename,line),
    )

  def onclick_breakpoint_de(self,pkg):
    ''' Disable/enable breakpoint'''
    raise NotImplementedError
    breakpoint_queue.process()

  def set_color(self,pkg):
    self.send(pkg)

  def terminate(self):
    pass


