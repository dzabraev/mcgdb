#!/usr/bin/env python
#coding=utf8

import argparse,pickle,sys,termios

ESC='\x1b'
CSI=ESC+'['

def read_char():
  ch = lambda : sys.stdout.read(1)
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

def make_terminal():
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


def to_control_sequence(screen):
  cols=screen.cols
  rows=screen.rows
  for row in range(rows):
    for col in range(cols):
      char = screen[row][col]
      sys.stdout.write(char.data)
    sys.stdout.write('\r\n')

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('play_journal',help='read screenshots from given file')
  parser.add_argument('--action_num',help='show screenshots starts with given number')
  args = parser.parser_args()
  while open(args.play_journal) as f:
    play_journal = pickle.load(f)
  screenshots=[]
  if args.action_num:
    start_pos=None
  else:
    start_pos=0
  cnt=0
  for play_record in play_journal:
    for data in play_record:
      cnt+=1
      screenshots.append({
        'screenshot':data['screenshot'],
        'action_num':play_record['action_num'],
        'name':play_record['name'],
      })
      if start_pos is None and play_record['action_num']==args.action_num:
        start_pos=cnt
  if start_pos==None:
    print 'cant find record with action_num={}'.format(args.action_num)
    sys.exit(0)

  current = start_pos
  total = len(screenshots)
  print "\x1b[?47h" #alternate screen
  saved_attrs = make_terminal(sys.stdout.fileno())
  try:
    while True:
      sys.stdout.write('\x1bc') #clear screen
      sys.stdout.write('\x1b[1;1H') #goto left upper corner
      sys.stdout.write(to_control_sequence(screenshots[current]))
      ch = read_char()
      if ch==ARROW_LEFT:
        current = max(current-1,0)
      elif ch==ARROW_RIGHT:
        current = min(current+1,total)
  except:
    print "\x1b[?47l" #normal screen
    termios.tcsetattr(fd, termios.TCSADRAIN, saved_attrs)
    raise



if __name__ == "__main__":
  main()