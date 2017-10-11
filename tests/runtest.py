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

def is_valid_file(parser, arg):
  if not os.path.exists(arg):
    parser.error("The file %s does not exist!" % arg)
  return os.path.abspath(arg)

def main():
  parser=argparse.ArgumentParser()
  parser.add_argument('--test',action='append',choices=ALLTESTS)
  parser.add_argument('--output',default='mcgdb.sum')
  parser.add_argument('--delay',type=float,default=2)
  parser.add_argument('--mcgdb',help='path to mcgdb',
    default=os.path.join(os.path.dirname(os.getcwd()),'mcgdb'),
    type=lambda x: is_valid_file(parser, x),
  )
  args=parser.parse_args()

  mcgdb=args.mcgdb

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
#    'variables':{
#      'delay':0.2,
#    },
#    'variables.wait_change_bug_1':{
#      'delay':0.5,
#    },
  })

  for testname in testnames:
    testdir=os.path.join(TESTDIR,testname)
    print 'TESTING %s' % testname
    cwd=os.getcwd()
    os.chdir(testdir)
    status,msg = imp.load_source(testname,'runtest.py').runtest(mcgdb=mcgdb,delay=args.delay,**kwargs[testname])
    os.chdir(cwd)
    print '%s %s' % (stat_color(status),msg)
    output.write('%s %s\n' % (status,msg))
    stat[status]+=1

  print '\n\nSUMMARY:'
  for key,value in stat.iteritems():
    print '%s %s' % (stat_color(status),value)

  print '\n\n'
  print 'see %s' % args.output
  output.close()

if __name__=="__main__":
  main()