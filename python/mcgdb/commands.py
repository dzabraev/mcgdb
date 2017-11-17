#coding=utf8

import gdb
#from mcgdb import mcgdb_main
from mcgdb.common import McgdbMain

def start_with(arr,word):
  return [s for s in arr if s[:len(word)]==word]


class McgdbCompleter (gdb.Command):
  def __init__ (self):
    super (McgdbCompleter, self).__init__ ("mcgdb", gdb.COMMAND_USER, gdb.COMPLETE_COMMAND, True)

class CmdOpenWindow (gdb.Command):
  """ Open mcgdb main window with current source file and current execute line

      Options:
      --manually if specified, then gdb will not start window, instead
          gdb only print shell command. User must manually copypaste given
          command into another terminal.
  """

  def __init__ (self):
    super (CmdOpenWindow, self).__init__ ("mcgdb open", gdb.COMMAND_USER)
    self.permissible_options=['--manually']
    self.types=['src', 'aux','asm']

  def invoke (self, arg, from_tty):
    self.dont_repeat()
    args=arg.split()
    if len(args)==0:
      print 'number of args must be >0'
      return
    type=args[0]
    options=args[1:]
    unknown_options=[opt for opt in options if opt not in self.permissible_options]
    if len(unknown_options) > 0:
      print 'unknown options: {}'.format(unknown_options)
    manually=('--manually' in options)
    if type not in self.types:
      print '`type` should be in {}'.format(self.types)
      return
    McgdbMain().open_window(type,manually=manually)

  def complete(self,text,word):
    complete_part = text[:len(text)-len(word)]
    narg=len(complete_part.split())
    if narg==0:
      return start_with(self.types,word)
    if narg >= 1:
      return gdb.COMPLETE_NONE








