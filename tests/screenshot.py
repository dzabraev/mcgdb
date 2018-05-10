#!/usr/bin/env python
#coding=utf8

import argparse,pickle,sys,copy,pyte.screens,curses,re,imp,os,itertools

from common import file_to_modname

warnings=[]

def is_buffers_equals(b1,b2,b1prev,b2prev,columns,lines,tostring,regexes,overlay_regexes):
  mcoords = matched_coords(b1,b1prev,lines,columns,tostring,regexes,overlay_regexes) | \
            matched_coords(b2,b2prev,lines,columns,tostring,regexes,overlay_regexes)
  for col in range(columns):
    for row in range(lines):
      if not b1[row][col]==b2[row][col] and (row,col) not in mcoords:
        return False
  return True


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


def get_tostring(name):
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
      for l1,l2 in regex(strbuf):
        for l in range(l1,l2):
          regex_matched.add(linear_to_yx(l,sbuf))
  return regex_matched

def get_diff_coord(b1,b2,lines,columns):
  diff=set()
  for col in range(columns):
    for row in range(lines):
      if b1[row][col]!=b2[row][col]:
        diff.add((row,col))
  return diff


def matched_coords(b,bprev,lines,columns,tostring,regexes,overlay_regexes):
  if bprev is not None:
    sprev=split_dummy(b)[0]['str']
    if any(itertools.imap(lambda x:x(sprev), overlay_regexes)):
      return get_matched_coord(bprev,tostring,regexes) - get_diff_coord(bprev,b,lines,columns)
  return get_matched_coord(b,tostring,regexes)


def diff(s1,s2,s1prev,s2prev,tostring=split_dummy,regexes=[],overlay_regexes=[],special_color=None):
  assert s1['cols']==s2['cols']
  assert s1['rows']==s2['rows']
  cols=s1['cols']
  rows=s1['rows']
  b1=s1['buffer']
  b2=s2['buffer']
  buffer=[]
  get_matched_coords = lambda s,sprev : matched_coords(s['buffer'],
    sprev.get('buffer') if sprev is not None else None,
    rows,cols,tostring,regexes,overlay_regexes)
  regex_matched  = get_matched_coords(s1,s1prev)
  regex_matched |= get_matched_coords(s2,s2prev)
  ((sp_bg,sp_fg),sp_coords) = special_color if special_color is not None else ((None,None),[])
  for row in range(rows):
    line=[]
    for col in range(cols):
      c1=b1[row][col]
      c2=b2[row][col]
      if (row,col) in regex_matched:
        bg,fg='green','white'
      elif (row,col) in sp_coords:
        if not c1==c2:
          bg,fg='red','white'
        else:
          bg,fg=sp_bg,sp_fg
      elif not c1==c2:
        bg,fg='red','white'
      else:
        bg,fg='black','white'
      line.append(pyte.screens.Char(c1.data, bg=bg,fg=fg))
    buffer.append(line)
  return {
    'cols':cols,
    'rows':rows,
    'buffer':buffer,
  }


def print_screenshot(stdscr,sshot,y,x,redmark=(-1,-1), special_color=None):
  ((sp_bg,sp_fg),sp_coords) = special_color if special_color is not None else ((None,None),[])
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
  ry,rx = redmark
  redpair = get_color('red','black')
  for row in range(rows):
    if (row+1)%5==0:
      s=str(row+1)
      for i in range(len(s)):
        attr = redpair if ry==row+i+1 else 0
        stdscr.addch(y+row+i+1,x,s[i],attr)
    elif ry==row+1:
      stdscr.addch(y+row+1,x,' ',redpair)
  for col in range(cols):
    if (col+1)%5==0:
      s=str(col+1)
      for i in range(len(s)):
        attr = redpair if rx==col+i+1 else 0
        stdscr.addch(y,x+col+1+i,s[i],attr)
    elif rx==col+1:
      stdscr.addch(y,x+col+1,' ',redpair)

  for col in range(cols):
    for row in range(rows):
      char = buffer[row][col]
      if (row,col) in sp_coords:
        attr=get_color(sp_bg,sp_fg)
      else:
        attr=make_attr(char)
      stdscr.addch(y+row+1,
                   x+col+1,
                   charmap.get(char.data,char.data.encode('utf8')),
                   attr)
    # On Fedora
    # without refresh() curses prints same character at the same place,
    # ignoring y, x position. For ex, if we try to print qqq, it prints
    # exactly one q.



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

def regex_span(regex,s):
  regex.finditer(s)

def normalize_regexes(regexes):
  normalized=[]
  for regextr in regexes:
    name=regextr[0]
    matcher=regextr[1]
    if len(regextr)==3:
      rng=list(regextr[2])
    else:
      rng=None
    if type(matcher) in (str,unicode):
      regex=matcher
      normalized.append((
        name,
        (lambda regex:lambda x:map(lambda y:y.span(),re.compile(regex,re.MULTILINE).finditer(x)))(regex),
        rng,regex))
    else:
      #callable object
      normalized.append((name,matcher,rng))
  return normalized

def read_regexes(fname,name='regexes',default=[]):
  module=imp.load_source('regexes',fname)
  if not hasattr(module,name):
    return default
  return normalize_regexes(getattr(module,name))

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
        'streamto':record['record']['name']
      })
  return screenshots

def get_neigh(journal,idx,op):
  idx0=idx+op(1)
  r=journal[idx]
  if r is None:
    return None
  name=r['name']
  L=len(journal)
  while idx0>=0 and idx0<=L-1:
    neigh=journal[idx0]
    if neigh['name']==name:
      return journal[idx0]
    idx0+=op(1)

def get_prev(journal,idx): return get_neigh(journal,idx, lambda x:-x)
def get_next(journal,idx): return get_neigh(journal,idx, lambda x:x)



def match_regex_range(rng,idx):
  if rng is None:
    return True
  else:
    return idx in rng

def filter_regexes(regexes,name,idx):
  return map(lambda x:x[1],filter( lambda x: x[0]==name and match_regex_range(x[2],idx),regexes))

def get_plus(y,x):
  return (('yellow','black'),[(y,x-1),(y,x+1),(y,x),(y-1,x),(y+1,x)])

def get_click_coord(stream):
  if stream is None:
    return
  match=re.match('\x1b\[<0;(\d+);(\d+)M\x1b\[<0;(\d+);(\d+)m',stream)
  if match:
    c1,r1,c2,r2=match.groups()
    if r1==r2 and c1==c2:
      return (int(r1)-1,int(c1)-1)
  return None


def show(stdscr,journal,journal2=None,start=0,regexes=[],overlay_regexes=[]):
  idx=start
  total=len(journal)
  while True:
    stdscr.clear()
    r1next=get_next(journal,idx)
    name=journal[idx]['name']
    r1=journal[idx]
    if journal2:
      #do diff
      r2=journal2[idx]
      s1=r1['screenshot']
      s2=r2['screenshot']
      r1prev=get_prev(journal,idx)
      r2prev=get_prev(journal2,idx)
      s1prev = r1prev['screenshot'] if r1prev else None
      s2prev = r2prev['screenshot'] if r2prev else None
      print_screenshot(stdscr,s1,0,0)
      print_screenshot(stdscr,s2,0,s1['cols']+2)
      y=max(s1['rows'],s2['rows'])+2
      if s1['cols']==s2['cols'] and s1['rows']==s2['rows']:
        click=get_click_coord(r1next.get('stream')) if r1next is not None else None
        if click is not None and r1next['streamto']==r1['name']:
          special_color=get_plus(click[0],click[1])
        else:
          special_color=None
        cur_regexes=filter_regexes(regexes,name,idx)
        cur_overlay_regexes=filter_regexes(overlay_regexes,name,idx)
        tostring=get_tostring(name)
        print_screenshot(stdscr,
          diff(s1,s2,s1prev,s2prev,tostring=tostring,regexes=cur_regexes,overlay_regexes=cur_overlay_regexes,special_color=special_color),
          y,0)
        sdiff=diff(s2,s1,s2prev,s1prev,tostring=tostring,regexes=cur_regexes,overlay_regexes=cur_overlay_regexes,special_color=special_color)
        print_screenshot(stdscr,sdiff,y,s1['cols']+2)
        line=y+sdiff['rows']+1
      else:
        stdscr.addstr(y,0,'different sizes, cant do diff')
        line=y+1
    else:
      s1=journal[idx]['screenshot']
      click=get_click_coord(r1next.get('stream')) if r1next is not None else None
      if click is not None and r1next['streamto']==r1['name']:
        special_color=get_plus(click[0],click[1])
      else:
        special_color=None
      print_screenshot(stdscr,s1,0,0,special_color=special_color)
      line = s1['rows']+2 #last line
    stdscr.addstr(line,0,'')
    stdscr.addstr('action_num={}\n\r'.format(journal[idx]['action_num']))
    stdscr.addstr('{}/{}\n\r'.format(idx+1,total))
    if 'stream' in journal[idx]:
      stdscr.addstr('stream({to})={stream}\n\r'.format(
        stream=repr(journal[idx]['stream']),
        to=journal[idx]['streamto'],
      ))
      if r1next is not None and 'stream' in r1next:
        stdscr.addstr('stream_next({to})={stream}\n\r'.format(
          stream=repr(r1next['stream']),
          to=r1next['streamto']
        ))
    for warn in warnings:
      stdscr.addstr('WARNING: %s\n\r' % warn)
    idx0=idx
    while True:
      ch = stdscr.getch()
      if ch==curses.KEY_LEFT:
        idx = max(idx-1,0)
      elif ch==curses.KEY_RIGHT:
        idx = min(idx+1,total-1)
      elif ch==ord('/'):
        snum=''
        stdscr.addstr(line+4,0,'goto %s' % snum)
        clear_goto = lambda : stdscr.addstr(line+4,0,'            ')
        while True:
          ch=stdscr.getch()
          if ch==ord('\x1b'):
            break
          elif 0x30<=ch<=0x39:
            snum+=chr(ch)
            stdscr.addstr(line+4,0,'goto %s' % snum)
          elif ch==ord('\n'):
            if snum:
              idx=int(snum)-1
              idx=max(min(total-1,idx),0)
            clear_goto()
            break
          elif ch==curses.KEY_BACKSPACE:
            snum=snum[:-1]
            clear_goto()
            stdscr.addstr(line+4,0,'goto %s' % snum)
          else:
            clear_goto()
            break
      if idx!=idx0:
        break


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
    overlay_regexes=normalize_regexes(getattr(module_regexes,'overlay_regexes',[]))
  else:
    regexes=[]
    overlay_regexes=[]
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
    curses.wrapper(show,play_journal,play_journal2,start,regexes,overlay_regexes)
  except KeyboardInterrupt:
    pass


if __name__ == "__main__":
  main()