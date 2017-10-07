#!/usr/bin/env python
#coding=utf8

import argparse,pickle,signal,time,select,collections,copy,json,sys,os,imp

from common import Gdb,McgdbWin, file_to_modname

def play():
  parser = argparse.ArgumentParser()
  parser.add_argument('record_file', help='sequence of actions for gdb and windows', default='record_log.py',nargs='?')
  parser.add_argument('--output', help='this file will be contain screenshots', default='record.play')
  parser.add_argument('--delay',type=float,default=1,help='amount of seconds')
  parser.add_argument('--regexes',help='read regexes from given file and store them into output')
  args = parser.parse_args()
  if args.record_file==args.output:
    print 'record_file must be not equal output'
    sys.exit(0)
  print 'record_file=%s' % args.record_file
  print 'output=%s' % args.output
  journal=[]
  journal_play=[]
  delay = args.delay
  output = open(args.output,'wb')
  module_records = imp.load_source(file_to_modname(args.record_file),os.path.abspath(args.record_file))
  journal = module_records.journal

  if args.regexes:
    regexes=getattr(__import__(file_to_modname(args.regexes)),'REGEXES',[])
  else:
    regexes=[]
  gdb=Gdb()
  wins_with_name = collections.OrderedDict([(name,gdb.open_win(name)) for name in module_records.windows])
  entities=dict(wins_with_name, gdb=gdb)
  fd_to_win=dict(map(lambda x: (x.master_fd,x), wins_with_name.values()))
  rlist = list(fd_to_win.keys())
  record_cnt=0
  record_total = len(journal)
  for record in journal:
    record_cnt+=1
    print '{: 5d}/{: 5d}\r'.format(record_cnt,record_total),
    sys.stdout.flush()
    name=record['name']
    action_num = record['action_num']
    if 'stream' in record:
      entities[name].send(record['stream'])
    elif 'sig' in record:
      sig=record['sig']
      if sig==signal.SIGWINCH:
        wins_with_name[name].resize(cols=record['col'],rows=record['row'])
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
      cols=win.screen.columns
      rows=win.screen.lines
      screenshots.append({
          'buffer':copy_buffer(win.screen.buffer,cols,rows),
          'cols':cols,
          'rows':rows,
          'name':name,
      })
    journal_play.append({
      'action_num':action_num,
      'screenshots':screenshots,
      'record':record,
    })
  print ''
  output.write(pickle.dumps({'journal_play':journal_play,'regexes':regexes}))

def copy_buffer(buf,cols,rows):
  sbuf=[]
  for row in range(rows):
    line=[]
    for col in range(cols):
      ch=buf[row][col]
      line.append(
        ch
      )
    sbuf.append(line)
  return sbuf


if __name__ == "__main__":
  play()

