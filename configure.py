#!/usr/bin/env python
#coding=utf8

import os,shutil
import sys
import argparse
import subprocess as sp

def configure_mcedit(args):
  path='/'.join(__file__.split('/')[:-1]) #mcgdb root
  configure=path+'/mc/configure'
  if path!='.':
    for fname in ['mcgdb.py', 'defines-mcgdb.gdb',  'mcgdb', 'install.py']:
      #shutil.copy('{}/{}'.format(path,fname),'./')
      os.symlink('{}/{}'.format(path,fname),fname)
  if not os.path.exists('obj-mc'):
    os.makedirs('obj-mc')
  savedcwd=os.getcwd()
  os.chdir('obj-mc')
  args.append('--program-prefix=mcgdb-')
  cmd='../{} {}'.format(configure,' '.join(args))
  print '`{}`'.format(cmd)
  os.system(cmd)
  os.chdir(savedcwd)

def generate_makefile(prefix):
  with open('Makefile','w') as f:
    f.write('''
all :
	make -C obj-mc
install :
	python install.py --prefix {prefix} --DESTDIR=$(DESTDIR)
'''.format(prefix=prefix))

def get_mc_location():
  res=sp.check_output('type mcedit',shell=True)
  path=res.split()[-1]
  rootpath='/'.join(path.split('/')[:-2])
  return rootpath

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--prefix",default='/usr/local')
  args=parser.parse_args()
  mc_prefix=get_mc_location()
  prefix=args.prefix
  configure_mcedit(sys.argv[1:] + ['--prefix',mc_prefix])
  generate_makefile(prefix)
  print 'install mcgdb to {}'.format(prefix)

if __name__ == "__main__":
  main()
