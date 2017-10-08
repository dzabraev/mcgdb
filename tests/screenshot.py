#!/usr/bin/env python
#coding=utf8

import argparse,pickle,sys,copy,pyte.screens,curses,re,imp,os

from common import file_to_modname

warnings=[]

def buffer_stringify_lines(buf):
  return map(lambda line : ''.join(map(lambda ch:ch.data,line)), buf)

def split_aux(buf):
  rows=len(buf)
  cols=len(buf[0])
  buf = buffer_stringify_lines(buf)
  return [
    {'str':map(lambda line: line[1:cols//2-1],buf[2:]),
      'A':(2,1),
      'B':(rows-1,cols//2-1)
    },
    {'str':map(lambda line: line[(cols//2)+1:cols],buf[2:]),
      'A':(2,(cols//2)+1),
      'B':(rows-1,cols)
    },
  ]

SPLITBUF={
  'aux':split_aux,
}


def split_dummy(buffer):
  return [
    {
      'str':'\n'.join(map(lambda x: ''.join(map(lambda y:y.data,x)), buffer)),
      'A':(0,0), #(y,x)
      'B':(len(buffer),len(buffer[0])),
    },
  ]


def get_splitbuf(name):
  return SPLITBUF.get(name,split_dummy)

def linear_to_yx(l,buf):
  A,B = buf['A'],buf['B']
  w=B[1]-A[1]
  x=A[1]+l%w
  y=A[0]+l//w
  return y,x

def get_matched_coord(buf,tostring,regexes):
  regex_matched=set()
  strbufs = tostring(buf)
  for sbuf in strbufs:
    strbuf=''.join(sbuf['str'])
    for regex in regexes:
      for l1,l2 in map(lambda x:x.span(),regex.finditer(strbuf)):
        for l in range(l1,l2):
          regex_matched.add(linear_to_yx(l,sbuf))
  return regex_matched

def diff(s1,s2,tostring=split_dummy,regexes=[]):
  assert s1['cols']==s2['cols']
  assert s1['rows']==s2['rows']
  cols=s1['cols']
  rows=s1['rows']
  b1=s1['buffer']
  b2=s2['buffer']
  buffer=[]
  regex_matched = get_matched_coord(b1,tostring,regexes)
  for row in range(rows):
    line=[]
    for col in range(cols):
      c1=b1[row][col]
      c2=b2[row][col]
      if (row,col) in regex_matched:
        line.append(pyte.screens.Char(c1.data,bg='green', fg='white'))
      elif not c1==c2:
        line.append(pyte.screens.Char(c1.data,bg='red', fg='white'))
      else:
        line.append(pyte.screens.Char(c1.data, bg='black', fg='white'))
    buffer.append(line)
  return {
    'cols':cols,
    'rows':rows,
    'buffer':buffer,
  }


def print_screenshot(stdscr,sshot,y,x):
  cols=sshot['cols']
  rows=sshot['rows']
  buffer=sshot['buffer']
  charmap={
    u'\u250c' : curses.ACS_ULCORNER,
    u'\u2510' : curses.ACS_URCORNER,
    u'\u2514' : curses.ACS_LLCORNER,
    u'\u2518' : curses.ACS_LRCORNER,
    u'\u2500' : curses.ACS_HLINE,
    u'\u2502' : curses.ACS_VLINE,
    u'\u251c' : 'X',
    u'\u2524' : 'X',
  }
  for row in range(rows):
    for col in range(cols):
      char = buffer[row][col]
      stdscr.addch(y+row,col+x,charmap.get(char.data,char.data.encode('utf8')),make_attr(char))


def make_attr(char):
  attrs = get_color(char.bg,char.fg)
  for name,attr in [
    ('bold',        curses.A_BOLD),
    ('underscore',  curses.A_UNDERLINE),
    ('reverse',     curses.A_REVERSE),
    ('italics',0),
    ('strikethrough',0),
  ]:
    if getattr(char,name):
      attrs |= attr
  if char.data in (u'\u250c',):
    attrs |= curses.A_ALTCHARSET
  return attrs

class Color(object):
  def __init__(self):
    self.colors={}
    self.seq=0
    self.map_clr={
      'black'   :   curses.COLOR_BLACK,
      'blue'    :   curses.COLOR_BLUE,
      'cyan'    :   curses.COLOR_CYAN,
      'green'   :   curses.COLOR_GREEN,
      'magenta' :   curses.COLOR_MAGENTA,
      'red'     :   curses.COLOR_RED,
      'white'   :   curses.COLOR_WHITE,
      'yellow'  :   curses.COLOR_YELLOW,
      'brown'   :   curses.COLOR_BLACK,
    }
  def __call__(self,bg,fg):
    bg = self.map_clr.get(bg,curses.COLOR_BLACK)
    fg = self.map_clr.get(fg,curses.COLOR_WHITE)
    key=(bg,fg)
    if key not in self.colors:
      self.seq+=1
      curses.init_pair(self.seq, fg, bg)
      self.colors[key]=curses.color_pair(self.seq)
    return self.colors[key]


get_color=Color()

def filter_by_winname(journal,name):
  for x in journal:
    x['screenshots'] = filter(lambda y:y['name']==name,x['screenshots'])
  return journal

def normalize_regexes(regexes):
  normalized=[]
  for regextr in regexes:
    name=regextr[0]
    regex=regextr[1]
    rng=None
    if len(regextr)==3:
      rng=list(regextr[2])
    normalized.append((name,re.compile(regex,re.MULTILINE),rng))
  return normalized

def read_regexes(fname):
  regexes=imp.load_source('regexes',fname).regexes
  return normalize_regexes(regexes)

def read_journal(name):
  with open(name,'rb') as f:
    d=pickle.load(f)
    return d['journal_play']

def linearize(journal):
  screenshots=[]
  for record in journal:
    for screenshot in record['screenshots']:
      screenshots.append({
        'screenshot':screenshot,
        'action_num':record['action_num'],
        'name':screenshot['name'],
        'stream':record['record'].get('stream',''),
      })
  return screenshots

def match_regex_range(rng,idx):
  if rng is None:
    return True
  else:
    return idx in rng

def filter_regexes(regexes,name,idx):
  return map(lambda x:x[1],filter( lambda x: x[0]==name and match_regex_range(x[2],idx),regexes))

def show(stdscr,journal,journal2=None,start=0,regexes=[]):
  idx=start
  total=len(journal)
  while True:
    stdscr.clear()
    if journal2:
      #do diff
      name=journal[idx]['name']
      sshot=journal[idx]['screenshot']
      sshot2=journal2[idx]['screenshot']
      print_screenshot(stdscr,sshot,0,0)
      print_screenshot(stdscr,sshot2,0,sshot['cols']+1)
      y=max(sshot['rows'],sshot2['rows'])+1
      if sshot['cols']==sshot2['cols'] and sshot['rows']==sshot2['rows']:
        cur_regexes=filter_regexes(regexes,name,idx)
        tostring=SPLITBUF.get(name,split_dummy)
        print_screenshot(stdscr,diff(sshot,sshot2,tostring=tostring,regexes=cur_regexes),y,0)
        sdiff=diff(sshot2,sshot,tostring=tostring,regexes=cur_regexes)
        print_screenshot(stdscr,sdiff,y,sshot['cols']+1)
        line=y+sdiff['rows']+1
      else:
        stdscr.addstr(y,0,'different sizes, cant do diff')
        line=y+1
    else:
      sshot=journal[idx]['screenshot']
      print_screenshot(stdscr,sshot,0,0)
      line = sshot['rows'] #last line
    stdscr.addstr(line,0,'')
    stdscr.addstr('action_num={}\n\r'.format(journal[idx]['action_num']))
    stdscr.addstr('{}/{}\n\r'.format(idx+1,total))
    for warn in warnings:
      stdscr.addstr('WARNING: %s\n\r' % warn)
    ch = stdscr.getch()
    if ch==curses.KEY_LEFT:
      idx = max(idx-1,0)
    elif ch==curses.KEY_RIGHT:
      idx = min(idx+1,total-1)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('play_journal',help='read screenshots from given file',default='record.play',nargs='?')
  parser.add_argument('play_journal2',help='if specified then evaluate diff between play_journal and play_journal2',nargs='?')
  parser.add_argument('--action_num',help='show screenshots starts with given action_num',type=int)
  parser.add_argument('--num',help='show screenshots starts with given screenshot number',type=int)
  parser.add_argument('--name',help='print screenshots only for window with name ')
  parser.add_argument('--regexes',help='python file contains regexes variable')
  args = parser.parse_args()

  play_journal = read_journal(args.play_journal)
  if args.regexes is not None:
    module_regexes = imp.load_source(file_to_modname(args.regexes),os.path.abspath(args.regexes))
    regexes=normalize_regexes(module_regexes.regexes)
  else:
    regexes=[]
  if args.play_journal2 is not None:
    play_journal2 = read_journal(args.play_journal2)
  else:
    play_journal2 = None

  if args.name is not None:
    filter_by_winname(play_journal,args.name)
    if play_journal2:
      filter_by_winname(play_journal2,args.name)

  play_journal=linearize(play_journal)
  if len(play_journal)==0:
    print 'length of {} equals 0'.format(args.play_journal)
    return
  if play_journal2 is not None:
    play_journal2=linearize(play_journal2)

  if play_journal2 is not None and len(play_journal)!=len(play_journal2):
    warnings.append('play_journal and play_journal2 has different size')
    l1,l2 = len(play_journal),len(play_journal2)
    if l1<l2:
      play_journal2=play_journal2[:l1]
    else:
      play_journal=play_journal[:l2]

  #check correctness
  if play_journal2 is not None:
    cnt=0
    for record,record2 in zip(play_journal,play_journal2):
      cnt+=1
      err=False
      msgs=[]
      if record['name']!=record2['name']:
        msgs.append('different win names in linenumber {num}')
      if record['action_num']!=record2['action_num']:
        msgs.append('different action_num in line number {num}')
      if err:
        for msg in msgs:
          print(msg.format(num=cnt))
        print(repr(record))
        print(repr(record2))
        sys.exit(0)


  start=0
  if args.num is not None:
    start = min(max(args.num,0),len(play_journal)-1)
  elif args.action_num is not None:
    for idx,record in enumerate(play_journal):
      if record['action_num']==args.action_num:
        start=idx
        break

  try:
    curses.wrapper(show,play_journal,play_journal2,start,regexes)
  except KeyboardInterrupt:
    pass


if __name__ == "__main__":
  main()