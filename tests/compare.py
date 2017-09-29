#!/usr/bin/env python
#coding=utf8

import argparse,sys,termcolor

from screenshot import read_journal, linearize, filter_regexes, get_matched_coord, get_splitbuf

def equals(r1,r2,regexes=[],tostring=None):
  s1=r1['screenshot']
  s2=r2['screenshot']
  if s1['cols']!=s2['cols'] or s1['rows']!=s2['rows']:
    return False
  cols=s1['cols']
  rows=s1['rows']
  b1=s1['buffer']
  b2=s2['buffer']
  regex_matched = get_matched_coord(b1,tostring,regexes)
  for col in range(cols):
    for row in range(rows):
      if b1[row][col]!=b2[row][col]:
        return False
  return True

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('journal1')
  parser.add_argument('journal2')
  parser.add_argument('--output',type=file,default=sys.stdout)
  parser.add_argument('--color_disable',action='store_true')
  parser.add_argument('--name',help='name of window')
  args = parser.parse_args()

  colorize=not args.color_disable

  regexes1,journal1 = read_journal(args.journal1)
  _regexes2,journal2 = read_journal(args.journal2)

  journal1=linearize(journal1)
  journal2=linearize(journal2)

  if args.name is not None:
    f=lambda x:x['name']==args.name
    journal1=filter(f,journal1)
    journal2=filter(f,journal2)

  l1,l2 = len(journal1),len(journal2)
  if l1<l2:
    journal1+=[None]*(l2-l1)
  else:
    journal2+=[None]*(l1-l2)

  assert len(journal1)==len(journal2)

  stat={'PASS':0,'FAIL':0}
  for idx,(r1,r2) in enumerate(zip(journal1,journal2)):
    name=r1['name']
    cur_regexes=filter_regexes(regexes1,name,idx)
    tostring=get_splitbuf(name)
    if equals(r1,r2,regexes=cur_regexes,tostring=tostring):
      msg='PASS'
      if colorize:
        msg=termcolor.colored(msg,'green')
      stat['PASS']+=1
    else:
      msg='FAIL'
      if colorize:
        msg=termcolor.colored(msg,'red')
      stat['FAIL']+=1
    msg+=' action_num={action_num: <5} name={name: <5} num={num: <5} stream={stream}'.format(
      num=idx,
      action_num=r1['action_num'],
      name=r1['name'],
      stream=repr(r1['stream']),
    )
    print (msg)
  print '\n\n'
  msg='TOTAL: {}'.format(sum(stat.values())); print msg
  msg='PASS:  {}'.format(stat['PASS']); print termcolor.colored(msg,'green') if colorize else msg
  msg='FAIL:  {}'.format(stat['FAIL']); print termcolor.colored(msg,'red')   if colorize else msg

if __name__ == "__main__":
  main()