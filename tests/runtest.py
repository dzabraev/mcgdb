#!/usr/bin/env python
#coding=utf8

import argparse,imp,termcolor,collections,os,sys

TESTDIR='testsuite'

def stat_color(status):
  colors={
    'FAIL':'red',
    'PASS':'green',
  }
  return termcolor.colored(status,colors.get(status))

ALLTESTS=[
  'variables.wait_change_bug_1',
  'variables',
]

def main():
  parser=argparse.ArgumentParser()
  parser.add_argument('--test',action='append',choices=ALLTESTS)
  parser.add_argument('--output',default='mcgdb.sum')
  args=parser.parse_args()

  os.environ['PATH'] = ':'.join([os.environ['PATH'],os.getcwd(),os.path.dirname(os.getcwd())])
  sys.path+=[
    os.getcwd(),
    os.path.dirname(os.getcwd()),
  ]

  output = open(args.output,'wb')

  if not args.test:
    testnames=ALLTESTS
  else:
    testnames=args.test


  stat=collections.defaultdict(int)

  kwargs=collections.defaultdict(dict,{
    'variables':{
      'delay':0.2,
    }
  })

  for testname in testnames:
    testdir=os.path.join(TESTDIR,testname)
    print 'TESTING %s' % testname
    cwd=os.getcwd()
    os.chdir(testdir)
    status,msg = imp.load_source(testname,'runtest.py').runtest(**kwargs[testname])
    os.chdir(cwd)
    print '%s %s' % (stat_color(status),msg)
    output.write('%s %s' % (status,msg))
    stat[status]+=1

  print '\n\nSUMMARY:'
  for key,value in stat.iteritems():
    print '%s %s' % (stat_color(status),value)

  print '\n\n'
  print 'see %s' % args.output
  output.close()

if __name__=="__main__":
  main()