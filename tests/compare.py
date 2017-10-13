#!/usr/bin/env python
#coding=utf8

import argparse,sys,termcolor,os,itertools

from screenshot import  read_journal, linearize, filter_regexes, matched_coords, \
                        read_regexes, get_prev, get_diff_coord, get_tostring, is_buffers_equals

status_code={
  'PASS':0,
  'FAIL':1,
}


def equals(r1,r2,r1prev,r2prev,regexes=[],tostring=None,overlay_regexes=[]):
  s1=r1['screenshot']
  s2=r2['screenshot']
  if s1['cols']!=s2['cols'] or s1['rows']!=s2['rows']:
    return False
  cols=s1['cols']
  rows=s1['rows']
  b1=s1['buffer']
  b2=s2['buffer']
  s1prev = r1prev['screenshot'] if r1prev is not None else None
  s2prev = r2prev['screenshot'] if r2prev is not None else None
  regex_matched2 = matched_coords(s2,s2prev,tostring,regexes,overlay_regexes)
  regex_matched1 = matched_coords(s1,s1prev,tostring,regexes,overlay_regexes)

  for col in range(cols):
    for row in range(rows):
      if b1[row][col]!=b2[row][col] and (row,col) not in regex_matched1 and (row,col) not in regex_matched2:
        return False
  return True

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('journal1')
  parser.add_argument('journal2')
  parser.add_argument('--output',type=argparse.FileType('w'),default=sys.stdout)
  parser.add_argument('--color_disable',action='store_true')
  parser.add_argument('--name',help='name of window')
  parser.add_argument('--regexes')
  args = parser.parse_args()
  output=args.output
  colorize=not args.color_disable
  return compare(   journal1=args.journal1,
                    journal2=args.journal2,
                    output=output,
                    colorize=colorize,
                    winname=args.name,
                    regexes=args.regexes
                )


def compare(journal1,journal2,output,colorize=True,winname=None,regexes=None):
  fname_journal1 = journal1
  fname_journal2 = journal2
  fname_regexes  = regexes
  journal1 = linearize(read_journal(journal1))
  journal2 = linearize(read_journal(journal2))

  if regexes is not None:
    regexes=read_regexes(fname_regexes)
    overlay_regexes=read_regexes(fname_regexes,name='overlay_regexes',default=[])
  else:
    regexes=[]
    overlay_regexes=[]

  if winname is not None:
    f=lambda x:x['name']==winname
    journal1=filter(f,journal1)
    journal2=filter(f,journal2)

  l1,l2 = len(journal1),len(journal2)
  if l1<l2:
    journal1+=[None]*(l2-l1)
  else:
    journal2+=[None]*(l1-l2)

  assert len(journal1)==len(journal2)

  stat={'PASS':0,'FAIL':0}
  PASS=termcolor.colored('PASS','green') if colorize else 'PASS'
  FAIL=termcolor.colored('FAIL','red')   if colorize else 'FAIL'
  #for idx,(r1,r2,r2pev) in enumerate(zip(journal1,journal2,[None]+journal2[1:])):
  for idx in range(len(journal1)):
    r1 = journal1[idx]
    r2 = journal2[idx]
    r1prev = get_prev(journal1,idx)
    r2prev = get_prev(journal2,idx)
    if r1 is None or r2 is None:
      msg=FAIL
      stat['FAIL']+=1
      continue
    else:
      name=r1['name']
      cur_regexes=filter_regexes(regexes,name,idx)
      cur_overlay_regexes=filter_regexes(overlay_regexes,name,idx)
      tostring=get_tostring(name)
      #if equals(r1,r2,r1prev,r2prev,regexes=cur_regexes,tostring=tostring,overlay_regexes=cur_overlay_regexes):
      b1=r1['screenshot']['buffer']
      b2=r2['screenshot']['buffer']
      b1prev=r1prev['screenshot']['buffer'] if r1prev else None
      b2prev=r2prev['screenshot']['buffer'] if r2prev else None
      columns=r1['screenshot']['cols']
      lines=r1['screenshot']['rows']
      if  r1['screenshot']['cols']==r2['screenshot']['cols'] and \
          r1['screenshot']['rows']==r2['screenshot']['rows'] and \
          is_buffers_equals(b1,b2,b1prev,b2prev,columns,lines,tostring,
            regexes=cur_regexes,
            overlay_regexes=cur_overlay_regexes
          ):
        msg=PASS
        stat['PASS']+=1
      else:
        msg=FAIL
        stat['FAIL']+=1
    msg+=' action_num={action_num: <5} name={name: <5} num={num: <5} stream={stream}'.format(
      num=idx,
      action_num=r1['action_num'],
      name=r1['name'],
      stream=repr(r1['stream']),
    )
    output.write(msg+'\n')
  output.write('\n\n')
  msg='TOTAL: {}\n'.format(sum(stat.values()))
  output.write(msg)
  msg='PASS:  {}\n'.format(stat['PASS'])
  output.write(termcolor.colored(msg,'green') if colorize else msg)
  msg='FAIL:  {}\n'.format(stat['FAIL'])
  output.write(termcolor.colored(msg,'red')   if colorize else msg)
  res='FAIL' if stat['FAIL']>0 else 'PASS'
  output.write('\nsee diff: `python screenshot.py {} {} {}`\n\n'.format(
    os.path.abspath(fname_journal1),
    os.path.abspath(fname_journal2),
    '--regexes={}'.format(os.path.abspath(fname_regexes)) if fname_regexes else '',
  ))
  return res

if __name__ == "__main__":
  main()
