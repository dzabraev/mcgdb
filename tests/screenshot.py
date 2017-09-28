#!/usr/bin/env python
#coding=utf8

import argparse,pickle,sys,termios, copy

ESC='\x1b'
CSI=ESC+'['
QUIT='q'

def read_char():
  ch = lambda : sys.stdin.read(1)
  char = ch()
  if char == ESC:
    char = ch()
    if char == '[':
      char = CSI
    else:
      return ESC+char
    char = ch()
    return CSI+char
  else:
    return char

ARROW_RIGHT=CSI+'C'
ARROW_LEFT=CSI+'D'

def make_terminal(fd):
  [iflag, oflag, cflag, lflag, ispeed, ospeed, cc] = list(range(7))
  raw = termios.tcgetattr(fd)
  saved = copy.deepcopy(raw)
#  raw[iflag] &=~ (termios.BRKINT | termios.INPCK |
#                 termios.ISTRIP | termios.IXON)
#  raw[oflag] &=~ (termios.OPOST)
#  raw[cflag] &=~ (termios.CSIZE|termios.PARENB)
#  raw[cflag] |=  (termios.CS8)
  raw[lflag] &=~ (termios.ICANON|termios.ECHO|
                 termios.IEXTEN|(termios.ISIG*1))
  raw[cc][termios.VMIN] = 1
  raw[cc][termios.VTIME] = 0
  termios.tcsetattr(fd, termios.TCSADRAIN, raw)
  return saved


def clr(name):
  m={
    'brown':'rosy_brown',
  }
  return m.get(name,name)

def to_control_sequence(screen):
  from colored import fg,bg,attr
  res=''
  cols=screen['cols']
  rows=screen['rows']
  buffer=screen['buffer']
  for row in range(rows):
    for col in range(cols):
      char = buffer[row][col]
      res+=fg(clr(char.fg))+bg(clr(char.bg))
      for name in ['bold','italics','underscore','strikethrough','reverse']:
        if getattr(char,name):
          res+=attr(name)
      res+=char.data.encode('utf8')
      res+=attr('reset')
    res+='\r\n'
  res+=attr('reset')
  return res

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('play_journal',help='read screenshots from given file',default='record.play',nargs='?')
  parser.add_argument('--action_num',help='show screenshots starts with given number',type=int)
  parser.add_argument('--num',help='screenshot number',type=int)
  parser.add_argument('--name',help='print screenshots only for window with name ')
  args = parser.parse_args()
  with open(args.play_journal) as f:
    play_journal = pickle.load(f)
  if args.name:
    def upd(x):
      x['screenshots'] = filter(lambda y:y['name']==args.name,x['screenshots'])
      return x
    play_journal=map(upd,play_journal)
  screenshots=[]
  if args.action_num:
    start_pos=None
  else:
    start_pos=args.num if args.num is not None else 0
  cnt=0
  for play_record in play_journal:
    for screenshot in play_record['screenshots']:
      cnt+=1
      screenshots.append({
        'screenshot':screenshot,
        'action_num':play_record['action_num'],
        'name':screenshot['name'],
      })
      if start_pos is None and play_record['action_num']==args.action_num:
        start_pos=cnt
  if start_pos==None:
    print 'cant find record with action_num={}'.format(args.action_num)
    sys.exit(0)

  current = start_pos
  prev=None
  total = len(screenshots)
  print "\x1b[?47h" #alternate screen
  saved_attrs = make_terminal(sys.stdout.fileno())
  try:
    while True:
      if current!=prev:
        sys.stdout.write('\x1bc') #clear screen
        sys.stdout.write('\x1b[1;1H') #goto left upper corner
        screenshot=screenshots[current]
        sys.stdout.write(to_control_sequence(screenshot['screenshot']))
        sys.stdout.write('action_num={}\r\nname={}\r\n{current}/{total}'.format(
          screenshot['action_num'],
          screenshot['name'],
          current=current+1,
          total=total,
        ))
        prev=current
      ch = read_char()
      if ch==ARROW_LEFT:
        current = max(current-1,0)
      elif ch==ARROW_RIGHT:
        current = min(current+1,total-1)
      elif ch==QUIT:
        break
  except Exception:
    print "\x1b[?47l" #normal screen
    termios.tcsetattr(sys.stdout.fileno(), termios.TCSADRAIN, saved_attrs)
    raise
  else:
    print "\x1b[?47l" #normal screen
    termios.tcsetattr(sys.stdout.fileno(), termios.TCSADRAIN, saved_attrs)



if __name__ == "__main__":
  main()