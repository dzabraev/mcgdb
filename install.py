#coding=utf8

import os,shutil
import sys
import argparse

def make_path(path):
  if not os.path.exists(path):
    os.makedirs(path)

def make_path_file(fname):
  path='/'.join(fname.split('/')[:-1])
  make_path(path)

def get_files(prefix):
  global DESTDIR
  files={
    'mcgdb-mcedit'     :('obj-mc/src/mc'    ,   '{}/bin/mcgdb-mcedit'.format(              prefix) ,   0555),
    'mcgdb'            :(None               ,   '{}/bin/mcgdb'.format(                     prefix) ,   0444),
    'mcgdb.py'         :('mcgdb.py'         ,   '{}/share/mcgdb/mcgdb.py'.format(          prefix) ,   0444),
    'defines-mcgdb.gdb':('defines-mcgdb.gdb',   '{}/share/mcgdb/defines-mcgdb.gdb'.format( prefix) ,   0444),
    'startup.gdb'      :(None               ,   '{}/share/mcgdb/startup.gdb'.format(       prefix) ,   0444),
  }
  return files

def install(prefix):
  files=get_files(prefix)
  for fname in files:
    src,dst,mode=files[fname]
    dst=DESTDIR+dst
    if src==None:
      continue
    if os.path.exists(dst):
      os.remove(dst)
    make_path_file(dst)
    shutil.copy(src,dst)
    os.chmod(dst,mode)
  os.system('''sed 's#PATH_TO_MC=.*#PATH_TO_MC="{mcedit}"#' {dst} -i'''.format(
    dst=DESTDIR+files['mcgdb.py'][1],
    mcedit=files['mcgdb-mcedit'][1],
  ))
  os.system('''sed 's#PATH_TO_DEFINES_MCGDB=.*#PATH_TO_DEFINES_MCGDB="{defines}"#' {dst} -i'''.format(
    dst=DESTDIR+files['mcgdb.py'][1],
    defines=files['defines-mcgdb.gdb'][1],
  ))
  with open(DESTDIR+files['startup.gdb'][1],'w') as f:
    f.write('''
source {mcgdb_py}
python
mc()
mcgdb_main_window()
end
'''.format(mcgdb_py=files['mcgdb.py'][1]))
  if os.path.exists(DESTDIR+files['mcgdb'][1]):
    os.remove(DESTDIR+files['mcgdb'][1])
  with open(DESTDIR+files['mcgdb'][1],'w') as f:
    f.write('''#!/usr/bin/env bash
gdb $@ -x {startup}
'''.format(startup=files['startup.gdb'][1]))
  os.chmod(DESTDIR+files['mcgdb'][1],0555)


def remove(prefix):
  pass

def main():
  global DESTDIR
  parser = argparse.ArgumentParser()
  parser.add_argument("--prefix")
  parser.add_argument("--DESTDIR",default='')
  args=parser.parse_args()
  prefix=args.prefix
  DESTDIR=args.DESTDIR
  if len(DESTDIR)>0 and DESTDIR[-1]=='/':
    DESTDIR=DESTDIR[:-1]
  install(prefix)

if __name__ == "__main__":
  main()