#!/usr/bin/env python
#coding=utf8

import argparse

from .common import Gdb,McgdbWin

def play():
  parser = argparse.ArgumentParser()
  parser.add_argument('--record_file', help='sequence of actions for gdb and windows',nargs=1)
  parser.add_argument('--output', help='this file will be contain screenshots',nargs=1)
  parser.add_argument('--delay',type=float,default=1,help='amount of seconds',nargs=1)
  args = parse.parse_args()
  journal=[]
  delay = args.delay
  output = open(args.output,'wb')
  with open(args.record_file) as f:
    for line in f.readlines():
      journal.append(json.loads(line[:-1]))
  screenshots = []
  gdb=Gdb()
  aux=gdb.open_win('aux')
  asm=gdb.open_win('asm')
  src=gdb.open_win('src')
  entitiens = {
    'aux':aux,
    'asm':asm,
    'src':src,
    'gdb':gdb,
  }
  wins_with_name = {
    'aux':aux,
    'asm':asm,
    'src':src,
  }
  wins = [aux,asm,src]
  fd_to_win=dict(map(lambda x: (x.master_fd,x), wins))
  rlist = list(fd_to_win.keys())
  record_cnt=0
  record_total = len(journal)
  for record in journal:
    record_cnt+=1
    print '\r{: 5d}/{: 5d}'.format(record_cnt,record_total)
    name=record['name']
    action_num = record['action_num']
    if 'stream' in record:
      entities[name].send(record['stream'])
    #collect window output
    t0 = time.time()
    while True:
      d = time.time() - t0 - delay
      if d<=0:
        break
      ready,[],[] = select.select(rlist,[],[],d)
      for fd in ready:
        fd_to_win[fd].recvfeed()
    #take screenshots
    for name,win in wins_with_name.iteritems():
      screenshots.append({
        'action_num':action_num,
        'screenshot':win.screenshot(),
        'name':name,
      })

if __name__ == "__main__":
  play()

