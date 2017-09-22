#!/usr/bin/env python
#coding=utf8

import argparse

from .common import Gdb,McgdbWin

def play():
  parser = argparse.ArgumentParser()
  parser.add_argument('record_file')
  args = parse.parse_args()
  journal=[]
  with open(args) as f:
    for line in f.readlines():
      journal.append(json.loads(line[:-1]))
  gdb=Gdb()
  for record in journal:
    


if __name__ == "__main__":
  play()