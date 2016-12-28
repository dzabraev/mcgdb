#coding=utf8

import os,shutil
import sys

def make_path(path):
  if not os.path.exists(path):
    os.makedirs(path)

def get_files(prefix):
  files={
    'mcgdb-mcedit'     :('mc/src/mcgdb-mc'  ,   '{}/bin/mcgdb-mcedit'.format(prefix)                ,   0777),
    'mcgdb'            :('mcgdb'            ,   '{}/bin/mcgdb'.format(prefix)                       ,   0777),
    'mcgdb.py'         :('mcgdb.py'         ,   '{}/share/mcgdb/mcgdb.py'.format(prefix)            ,   0777),
    'defines-mcgdb.gdb':('defines-mcgdb.gdb',   '{}/share/mcgdb/defines-mcgdb.gdb'.format(prefix)   ,   0777),
    'startup.gdb'      :('startup.gdb'      ,   '{}/share/mcgdb/startup.gdb'.format(prefix)         ,   0777),
  }
  return files

def install(prefix):
  make_path(prefix+'/bin')
  make_path(prefix+'/share')
  make_path(prefix+'/share/mcgdb')
  files=get_files(prefix)
  for fname in files:
    src,dst,mode=files[fname]
    if os.path.exists(dst):
      os.remove(dst)
    shutil.copy(src,dst)
    os.chmod(dst,mode)
  os.system("sed 's/PATH_TO_MC=.*/PATH_TO_MC={mcedit}/' {dst}".format(
    dst=files['mcgdb.py'][1],
    mcedit=files['mcgdb-mcedit'][1],
  ))
  os.system("sed 's/PATH_TO_DEFINES_MCGDB=.*/PATH_TO_DEFINES_MCGDB={defines}/' {dst}".format(
    dst=files['mcgdb.py'][1],
    defines=files['defines-mcgdb.gdb'][1],
  ))


def remove(prefix):
  pass

def main():
  prefix=''
  if len(sys.argv)>=3 and sys.argv[1]=='--prefix':
    prefix=sys.argv[2]
  install(prefix)

if __name__ == "__main__":
  main()