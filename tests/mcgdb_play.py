#!/usr/bin/env python
#coding=utf8

import argparse,pickle,signal,time,select,collections,copy,json,sys,os,imp,pprint,\
        itertools,pyte

from common import Gdb,McgdbWin, file_to_modname
from runtest import is_valid_file
from screenshot import read_journal, matched_coords, get_tostring, normalize_regexes, filter_regexes, is_buffers_equals

def get_databuffer_by_name(wait_record,name):
  for wr in wait_record['screenshots']:
    if wr['name']==name:
      return wr

def iter_buffer(buffer,columns,lines):
  return map(lambda line: map(lambda column:buffer[line][column],range(columns)),range(lines))


def compare(win,name,journal_play,wait_journal,record_idx,regexes,overlay_regexes):
  tostring=get_tostring(name)
  lines=win.screen.lines
  columns=win.screen.columns
  b1=copy_buffer(win.screen.buffer,columns,lines)
  etalon=get_databuffer_by_name(wait_journal[record_idx],name)
  b2=etalon['buffer']
  if record_idx>=1:
    b1prev=get_databuffer_by_name(journal_play[-1],name)['buffer']
    b2prev=get_databuffer_by_name(wait_journal[record_idx-1],name)['buffer']
  else:
    b1prev=None
    b2prev=None
  ok =  lines==etalon['rows'] and columns==etalon['cols'] and \
        is_buffers_equals(
          b1=b1,
          b2=b2,
          b1prev=b1prev,
          b2prev=b2prev,
          columns=columns,
          lines=lines,
          tostring=tostring,
          regexes=filter_regexes(regexes,name,record_idx),
          overlay_regexes=filter_regexes(overlay_regexes,name,record_idx)
        )
  return ok


def play():
  parser = argparse.ArgumentParser()
  parser.add_argument('record_file', help='sequence of actions for gdb and windows', default='record.py',nargs='?')
  parser.add_argument('--output', help='this file will be contain screenshots', default='record.play')
  parser.add_argument('--delay',type=float,default=1,help='amount of seconds')
  parser.add_argument('--regexes',help='read regexes from given file and store them into output')
  parser.add_argument('--wait',help='specify .play file',type=lambda x: is_valid_file(parser, x))
  parser.add_argument('--print_records',help='print records',action='store_true')
  parser.add_argument('--valgrind',help='path to file where valgrind log will be stored')
  parser.add_argument('--logging',help='path to file where mcgdb log will be stored')
  parser.add_argument('--wait_key',help='wait until you press any key then and runs test. You can attach gdb and press some key.',action='store_true')
  parser.add_argument('--mcgdb',help='path to mcgdb',
    default=os.path.join(os.path.dirname(os.getcwd()),'mcgdb'),
    type=lambda x: is_valid_file(parser, x),
  )
  args = parser.parse_args()
  mcgdb=args.mcgdb
  if args.record_file==args.output:
    print 'record_file must be not equal output'
    sys.exit(0)
  print 'record_file=%s' % args.record_file
  print 'output=%s' % args.output
  journal=[]
  journal_play=[]
  delay = args.delay
  module_records = imp.load_source(file_to_modname(args.record_file),os.path.abspath(args.record_file))
  journal = module_records.journal

  if args.regexes is not None:
    module_regexes = imp.load_source(file_to_modname(args.regexes),os.path.abspath(args.regexes))
    regexes=normalize_regexes(module_regexes.regexes)
    overlay_regexes=normalize_regexes(getattr(module_regexes,'overlay_regexes',[]))
  else:
    regexes=[]
    overlay_regexes=[]

  env={}
  if args.logging:
    env['DEBUG'] = args.logging
  gdb=Gdb(executable=mcgdb,env=env)

  wins_with_name = collections.OrderedDict([(name,gdb.open_win(name, valgrind=args.valgrind)) for name in module_records.windows])
  if args.wait:
    wait_journal = read_journal(args.wait)
    wait_status={}
  else:
    wait_journal = [None]*len(journal)
  entities=dict(wins_with_name, gdb=gdb)
  fd_to_win=dict(map(lambda x: (x.master_fd,x), wins_with_name.values()))
  fd_to_name=dict(map(lambda x: (x[1].master_fd,x[0]), wins_with_name.items()))
  rlist = list(fd_to_win.keys())
  record_cnt=0
  record_total = len(journal)
  output = open(args.output,'wb')

  if args.wait_key:
    for name,win in wins_with_name.iteritems():
      print 'name=%s PID=%s' % (name,win.pid)
    raw_input('enter any key')

  try:
    for record_idx,(record,wait_record) in enumerate(zip(journal,wait_journal)):
      record_cnt+=1
      print '{: 5d}/{: 5d}\r'.format(record_cnt,record_total),
      if args.print_records:
        print record
      sys.stdout.flush()
      name=record['name']
      action_num = record['action_num']
      if 'stream' in record:
        entities[name].send(record['stream'])
      elif 'sig' in record:
        sig=record['sig']
        if sig==signal.SIGWINCH:
          wins_with_name[name].resize(cols=record['col'],rows=record['row'])
      if args.wait:
        done={}
        for name in wins_with_name.keys():
          win=entities[name]
          done[name] = compare(win,name,journal_play,wait_journal,record_idx,regexes,overlay_regexes)
      #collect window output
      t0 = time.time()
      while True:
        if args.wait and all(done.values()):
          break
        d = t0 - time.time() + delay
        if d<=0:
          break
        ready,[],[] = select.select(rlist,[],[],d)
        for fd in ready:
          name=fd_to_name[fd]
          win=fd_to_win[fd]
          win.recvfeed()
          if args.wait:
            done[name] = compare(win,name,journal_play,wait_journal,record_idx,regexes,overlay_regexes)
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
  except Exception:
    print '\nerror while test execution'
    output.write(pickle.dumps({'journal_play':journal_play}))
    raise
  print ''
  output.write(pickle.dumps({'journal_play':journal_play}))

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

