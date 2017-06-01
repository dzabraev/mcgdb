#coding=utf8

import gdb
import os,stat

TMP_FILE_NAME="/tmp/mcgdb/mcgdb-tmp-file-{pid}.txt".format(pid=os.getpid())

from mcgdb.basewin import BaseWin
from mcgdb.common import breakpoint_queue
from mcgdb.common import gdb_print

class SrcWin(BaseWin):

  type='srcwin'
  startcmd='mcgdb open src'


  def __init__(self, **kwargs):
    super(SrcWin,self).__init__(**kwargs)
    self.exec_filename=None #текущему фрейму соответствует это имя файла с исходным кодом
    self.exec_line=None     #номер строки текущей позиции исполнения программы
    self.edit_filename=None #Файл, который открыт в редакторе. Отличие от self.exec_filename в
                            #том, что если исходник открыть нельзя, то открывается файл-заглушка.

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

  def update_current_frame(self):
    '''Данная функция извлекает из gdb текущий файл
        и номер строки исполнения. После чего, если необходимо, открывает
        файл с исходником в редакторе и перемещает экран к линии исполнения.
    '''
    filename,line = self.get_current_position()
    if (not filename and self.edit_filename!=TMP_FILE_NAME) or filename!=self.exec_filename:
      if self.edit_filename:
        #если в редакторе был открыт файл, то закрываем его.
        self.send({'cmd':'fclose'})
      if not filename or not os.path.exists(filename) or \
        not ( os.stat(filename).st_mode & stat.S_IFREG and \
              os.stat(filename).st_mode & stat.S_IREAD \
        ):
        #новый файл неизвестен, либо не существует, либо не является файлом.
        #открываем в редакторе заглушку
        dname=os.path.dirname(TMP_FILE_NAME)
        if not os.path.exists(dname):
          os.makedirs(dname)
        with open(TMP_FILE_NAME,'w') as f:
          if not filename:
            f.write('\nCurrent execution position and source file not known.\n')
          else:
            f.write('\nFilename {} not exists\n'.format(filename))
        self.send({
          'cmd'       :   'fopen',
          'filename'  :   TMP_FILE_NAME,
          'line'      :   1,
        })
        self.edit_filename=TMP_FILE_NAME
      else:
        #все нормально, файл существует, его можно прочитать
        self.send({
          'cmd'       :   'fopen',
          'filename'  :   filename,
          'line'      :   line if line!=None else 0,
        })
        self.edit_filename=filename
    if line!=self.exec_line and line!=None:
      self.send({'cmd':'set_curline',  'line':line})
    assert self.edit_filename!=None
    self.exec_filename=filename
    self.exec_line=line


  def update_breakpoints(self):
    normal=breakpoint_queue.get_bps_locs_normal(self.edit_filename)
    disabled=breakpoint_queue.get_bps_locs_disabled(self.edit_filename)
    wait_remove=breakpoint_queue.get_bps_locs_wait_remove(self.edit_filename)
    wait_insert=breakpoint_queue.get_bps_locs_wait_insert(self.edit_filename)
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
    line=pkg['line']
    if self.edit_filename==TMP_FILE_NAME:
      #в редакторе открыт файл-заглушка.
      #молча игнорируем попытки манипуляцией брейкпоинтами
      return
    breakpoint_queue.insert_or_delete(self.edit_filename,line)
    breakpoint_queue.process()
    return [{'cmd':'check_breakpoint'}]

  def onclick_breakpoint_de(self,pkg):
    ''' Disable/enable breakpoint'''
    raise NotImplementedError
    breakpoint_queue.process()

  def set_color(self,pkg):
    self.send(pkg)

  def terminate(self):
    try:
      os.remove(TMP_FILE_NAME)
    except:
      pass


