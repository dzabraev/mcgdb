#!/usr/bin/env python
#coding=utf8

import argparse,imp,termcolor,collections,os,sys,subprocess

import compare

TESTDIR='testsuite'

def stat_color(status):
  colors={
    'FAIL':'red',
    'PASS':'green',
  }
  return termcolor.colored(status,colors.get(status))

ALLTESTS=[
  'variables.wait_change_bug_1',
  'variables.expand_change_null_step',
  'variables.incompl_struct',
  'variables.int',
  'variables.void_star_const',
  'srcwin.common',
  'srcwin.frame-shell-cmd',
]


def do_cmd(cmd,check=True):
  print cmd
  fn = subprocess.check_call if check else subprocess.call
  return fn(cmd, shell=True)


def run_std_test(mcgdb,delay,logfile='logfile.log',wait=False,regexes='regexes.py',print_records=False):
  has_regexes=os.path.exists(regexes)
  if has_regexes:
    regexes = os.path.abspath(regexes)
  do_cmd('make clean')
  do_cmd('make')
  do_cmd("unxz --keep --force {record_orig_py_xz}".format(
    record_orig_py_xz = os.path.abspath('record.orig.play.xz'),
  ))
  cmd="mcgdb_play.py {record_orig} --delay={delay} --output={record_new} --mcgdb={mcgdb} {print_records}".format(
    record_orig=os.path.abspath('record.orig.py'),
    record_new=os.path.abspath('record.new.play'),
    delay=delay,
    mcgdb=mcgdb,
    print_records='--print_records' if print_records else '',
  )
  if wait:
    cmd+=' --wait=record.orig.play'
    if has_regexes:
      cmd+=' --regexes=%s' % regexes
  do_cmd(cmd,check=False)
  flog=open(logfile,'wb')
  kwargs={
      'journal1': 'record.orig.play',
      'journal2': 'record.new.play',
      'colorize': False,
      'output':   flog,
  }
  if has_regexes:
    kwargs['regexes']=regexes
  res=compare.compare(**kwargs)
  flog.close()
  return res,'See %s' % os.path.join(os.getcwd(),logfile)

def is_valid_file(parser, arg):
  if not os.path.exists(arg):
    parser.error("The file %s does not exist!" % arg)
  return os.path.abspath(arg)

def main():
  parser=argparse.ArgumentParser()
  parser.add_argument('--test',action='append',choices=ALLTESTS)
  parser.add_argument('--output',default='mcgdb.sum')
  parser.add_argument('--delay',type=float,default=2)
  parser.add_argument('--wait',action='store_false')
  parser.add_argument('--print_records',help='print records',action='store_true')
  parser.add_argument('--mcgdb',help='path to mcgdb',
    default=os.path.join(os.path.dirname(os.getcwd()),'mcgdb'),
    type=lambda x: is_valid_file(parser, x),
  )
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
  })

  for testname in testnames:
    testdir=os.path.join(TESTDIR,testname)
    print 'TESTING %s' % testname
    cwd=os.getcwd()
    os.chdir(testdir)
    kw=dict(mcgdb=args.mcgdb,
          delay=args.delay,
          wait=args.wait,
          print_records=args.print_records,
    )
    kw.update(kwargs[testname])
    if os.path.exists('runtest.py'):
      status,msg = imp.load_source(testname,'runtest.py').runtest(**kw)
    else:
      status,msg=run_std_test(**kw)
    os.chdir(cwd)
    print '%s %s' % (stat_color(status),msg)
    output.write('%s %s\n' % (status,msg))
    stat[status]+=1

  print '\n\nSUMMARY:'
  for key,value in stat.iteritems():
    print '%s %s' % (stat_color(key),value)

  print '\n\n'
  print 'see %s' % args.output
  output.close()

if __name__=="__main__":
  main()