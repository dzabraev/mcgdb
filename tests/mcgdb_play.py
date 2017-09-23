#!/usr/bin/env python
#coding=utf8

import argparse,pickle,signal,time,select,collections,copy,json

from common import Gdb,McgdbWin

def play():
  parser = argparse.ArgumentParser()
  parser.add_argument('record_file', help='sequence of actions for gdb and windows')
  parser.add_argument('output', help='this file will be contain screenshots')
  parser.add_argument('--delay',type=float,default=1,help='amount of seconds')
  args = parser.parse_args()
  journal=[]
  journal_play=[]
  delay = args.delay
  output = open(args.output,'wb')
  with open(args.record_file) as f:
    for line in f.readlines():
      journal.append(json.loads(line[:-1]))
  gdb=Gdb()
  aux=gdb.open_win('aux')
  asm=gdb.open_win('asm')
  src=gdb.open_win('src')
  entities = {
    'aux':aux,
    'asm':asm,
    'src':src,
    'gdb':gdb,
  }
  wins_with_name = collections.OrderedDict({
    'aux':aux,
    'asm':asm,
    'src':src,
  })
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
    elif 'sig' in record:
      sig=record['sig']
      if sig==signal.SIGWINCH:
        wins_with_name[name].display.resize(columns=record['col'],lines=record['row'])
    #collect window output
    t0 = time.time()
    while True:
      d = t0 - time.time() + delay
      if d<=0:
        break
      ready,[],[] = select.select(rlist,[],[],d)
      for fd in ready:
        fd_to_win[fd].recvfeed()
    #take screenshots
    screenshots=[]
    for name,win in wins_with_name.iteritems():
      screenshots.append({
        'screenshot':copy.deepcopy(win.screen.buffer.items()),
        'name':name,
      })
    journal_play.append({
      'action_num':action_num,
      'screenshots':screenshots,
    })
  output.write(pickle.dumps(journal_play))

if __name__ == "__main__":
  play()

