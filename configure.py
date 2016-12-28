#!/bin/evn python
#coding=utf8

import os,shutil
import sys

def configure_mcedit(args):
  path='/'.join(__file__.split('/')[:-1])
  configure=path+'/mc/configure'
  for fname in ['mcgdb.py', 'defines-mcgdb.gdb', 'startup.gdb', 'mcgdb']:
    shutil.copy('{}/{}'.format(path,fname),'./')
  if not os.path.exists('obj-mc'):
    os.makedirs('obj-mc')
  savedcwd=os.getcwd()
  os.chdir('obj-mc')
  cmd='../{} {}'.format(configure,' '.join(args))
  print '`{}`'.format(cmd)
  os.system(cmd)
  os.chdir(savedcwd)

def generate_makefile():
  with open('Makefile','w') as f:
    f.write('''
all :
	make -C obj-mc

    ''')

def main():
  configure_mcedit(sys.argv[1:])
  generate_makefile()

if __name__ == "__main__":
  main()
