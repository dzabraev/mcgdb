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




class CmdColor (gdb.Command):
  '''Change color in editor.
USAGE: mcgdb color type text_color background_color [attribs]

type={curline, bp_normal, bp_disabled, bp_wait_remove, bp_wait_insert}
COLOR={black, white, blue, yellow, red, ...}
attrib={bold, italic, underline, reverse, blink}
text_color: see COLOR set
background_color: see COLOR set
attribs: attrib1+...+attrinb
'''

  def __init__ (self):
    super (CmdColor, self).__init__ ('mcgdb color', gdb.COMMAND_USER)
    self.cbs={
      'curline'        : McgdbMain().set_color_curline,
      'bp_normal'      : McgdbMain().set_color_bp_normal,
      'bp_disabled'    : McgdbMain().set_color_bp_disabled,
      'bp_wait_remove' : McgdbMain().set_color_bp_wait_remove,
      'bp_wait_insert' : McgdbMain().set_color_bp_wait_insert,
    }
    self.colors=[
      'black', 'gray', 'red', 'brightred', 'green', 'brightgreen',
      'brown', 'yellow', 'blue', 'brightblue', 'magenta', 'brightmagenta',
      'cyan', 'brightcyan', 'lightgray', 'white',
    ]
    self.attribs= [
      'bold', 'italic', 'underline', 'reverse', 'blink',
    ]
    self.types=self.cbs.keys()

  def invoke (self, arg, from_tty):
    args=arg.split()
    if len(args)!=3 and len(args)!=4:
      print 'number of args must be 3 or 4'
      return
    if len(args)==3:
      type,text_color,background_color = tuple(args)
      attribs=None
    else:
      type,text_color,background_color,attribs = tuple(args)
    if type not in self.types:
      print '`type` should be in {}'.format(self.types)
      return
    if text_color not in self.colors:
      print '`text_color` should be in {}'.format(self.colors)
      return
    if background_color not in self.colors:
      print '`background_color` should be in {}'.format(self.colors)
      return
    if attribs:
      attribs_arr=attribs.split('+')
      for attrib in attribs_arr:
        if attrib not in self.attribs:
          print '`attrib` should be in {}'.format(self.attribs)
          return
    self.cbs[type](text_color,background_color,attribs)

  def complete(self,text,word):
    complete_part = text[:len(text)-len(word)]
    narg=len(complete_part.split())
    #gdb.write( 'nargs={narg} word=`{word}`'.format( word=word,narg=narg ) )
    if narg==0:
      return start_with(self.types,word)
    if narg==1 or narg==2:
      return start_with(self.colors,word)
    if narg==3:
      return start_with(self.attribs,word)
    if narg >= 4:
      return gdb.COMPLETE_NONE




