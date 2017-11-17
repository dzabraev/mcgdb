#coding=utf8


PATH_TO_DEFINES_MCGDB="__PATH_TO_DEFINES_MCGDB__"
PATH_TO_MC="__PATH_TO_MC__"

_dw={}

def init_commands():
  import mcgdb.commands, mcgdb.common
  global mcgdb_main
  mcgdb_main = mcgdb.common.McgdbMain()
  mcgdb.commands.McgdbCompleter()
  mcgdb.commands.CmdOpenWindow()


def init():
  init_commands()