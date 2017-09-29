#!/usr/bin/env python
#coding=utf8

import argparse,pickle,sys,copy,pyte.screens,curses

def diff(s1,s2):
  assert s1['cols']==s2['cols']
  assert s1['rows']==s2['rows']
  cols=s1['cols']
  rows=s1['rows']
  b1=s1['buffer']
  b2=s2['buffer']
  buffer=[]
  for row in range(rows):
    line=[]
    for col in range(cols):
      c1=b1[row][col]
      c2=b2[row][col]
      if not c1==c2:
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

def read_journal(name):
  with open(name,'rb') as f:
    return pickle.load(f)

def linearize(journal):
  screenshots=[]
  for record in journal:
    for screenshot in record['screenshots']:
      screenshots.append({
        'screenshot':screenshot,
        'action_num':record['action_num'],
        'name':screenshot['name'],
      })
  return screenshots



def show(stdscr,journal,journal2=None,start=0):
  idx=start
  total=len(journal)
  while True:
    if journal2:
      #do diff
      sshot=journal[idx]['screenshot']
      sshot2=journal2[idx]['screenshot']
      print_screenshot(stdscr,sshot,0,0)
      print_screenshot(stdscr,sshot2,0,sshot['cols']+1)
      y=max(sshot['rows'],sshot2['rows'])+1
      if sshot['cols']==sshot2['cols'] and sshot['rows']==sshot2['rows']:
        print_screenshot(stdscr,diff(sshot,sshot2),y,0)
        sdiff=diff(sshot2,sshot)
        print_screenshot(stdscr,sdiff,y,sshot['cols']+1)
        line=y+sdiff['rows']+1
      else:
        stdscr.addstr(y,0,'different sizes')
        line=y+1
    else:
      sshot=journal[idx]['screenshot']
      print_screenshot(stdscr,sshot,0,0)
      line = sshot['rows'] #last line
    stdscr.addstr(line,0,'')
    stdscr.addstr('action_num={}\n\r'.format(journal[idx]['action_num']))
    stdscr.addstr('{}/{}\n\r'.format(idx+1,total))
    ch = stdscr.getch()
    if ch==curses.KEY_LEFT:
      idx = max(idx-1,0)
    elif ch==curses.KEY_RIGHT:
      idx = min(idx+1,total-1)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('play_journal',help='read screenshots from given file',default='record.play',nargs='?')
  parser.add_argument('play_journal2',help='if specified then evaluate diff between play_journal and play_journal_correct',nargs='?')
  parser.add_argument('--action_num',help='show screenshots starts with given action_num',type=int)
  parser.add_argument('--num',help='show screenshots starts with given screenshot number',type=int)
  parser.add_argument('--name',help='print screenshots only for window with name ')
  args = parser.parse_args()

  play_journal = read_journal(args.play_journal)
  if args.play_journal2 is not None:
    play_journal2 = read_journal(args.play_journal2)
  else:
    play_journal2 = None

  if args.name is not None:
    filter_by_winname(play_journal,args.name)
    if play_journal2:
      filter_by_winname(play_journal2,args.name)

  play_journal=linearize(play_journal)
  if play_journal2 is not None:
    play_journal2=linearize(play_journal2)

  if play_journal2 is not None and len(play_journal)!=len(play_journal2):
    print('play_journal and play_journal2 has different size')
    sys.exit(0)

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
    curses.wrapper(show,play_journal,play_journal2,start)
  except KeyboardInterrupt:
    pass


if __name__ == "__main__":
  main()