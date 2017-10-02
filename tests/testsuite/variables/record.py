#coding=utf8

import re
HEXADDR='0x[0-9a-f]+'

def pattern_addr(pat):
  import re
  HEXADDR='0x[0-9a-f]+'
  return '(?<=%s)%s' % (re.escape(pat),HEXADDR)

def subarray_addr(pat):
  import re
  HEXADDR='0x[0-9a-f]+'
  return '(?<=%s)\*(%s)' % (re.escape(pat),HEXADDR)

REGEXES=[
    ('aux',pattern_addr('int (*)[3][3][3] arr = ')),
    ('aux',pattern_addr('incompl_struct * is = ')),
    ('aux',pattern_addr('incompl_union * iu = ')),
    ('aux',pattern_addr('int *** intarr3 = ')),
    ('aux',pattern_addr('const char (*)[4] const_charbuf = ')),
    ('aux',pattern_addr('int ** intarr = ')),
    ('aux','{}\s*{}{ADDR}\)'.re.escape('int ** intarr[0:2] = ['),re.escape('int * *(')),
    ('aux',pattern_addr('incompl_union ** is2 = ')),
    ('aux',pattern_addr('double * dblarr2 = ')),
    ('aux',pattern_addr('incompl_union ****** is6 = ')),
    ('aux',subarray_addr('incompl_union ***** ')),
    ('aux',subarray_addr('incompl_union **** ')),
    ('aux',subarray_addr('incompl_union *** ')),
    ('aux',subarray_addr('incompl_union ** ')),
    ('aux','{}\s*{ADDR},\s*{ADDR},\s*{ADDR},\s*{ADDR},\s*{ADDR}\s*\]'.format(re.escape('incompl_union ** *(0x613e60)[0:4] = ['),ADDR=HEXADDR)),
    ('aux',pattern_addr('mystruct (*)[2] darr = ')),
    ('aux',pattern_addr('const char *(*)[2] m_char_ptrbuf = ')),
    ('aux',pattern_addr('unsigned char (*)[4] ucharbuf = ')),
    ('aux',pattern_addr('mystruct * d = ')),
    ('aux',pattern_addr('char (*)[4] charbuf = ')),
    ('aux',pattern_addr('double * dblarr = ')),
    ('aux',pattern_addr('const char * longstr = ')),
    ('aux',pattern_addr('void * retval = ')),
]



journal=[
    {
        "action_num": 1, 
        "name": "gdb", 
        "stream": "file testsuite/variables/src/main\nb main\nrun"
    }, 
    {
        "action_num": 4, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 5, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 6, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 7, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 8, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 9, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 10, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 11, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 12, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 13, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 14, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 15, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 16, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 17, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 18, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 19, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 20, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 21, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 22, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 23, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 24, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 25, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 26, 
        "name": "aux", 
        "stream": "\u001b[<65;22;9M"
    }, 
    {
        "action_num": 27, 
        "name": "aux", 
        "stream": "\u001b[<0;54;1M\u001b[<0;54;1m"
    }, 
    {
        "action_num": 28, 
        "name": "aux", 
        "stream": "\u001b[<0;47;1M\u001b[<0;47;1m"
    }
]