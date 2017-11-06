#coding=utf8
import re

ADDR_REGEX='(0x)?[0-9a-fA-F]+'
SLICE_REGEX='\[\d(:\d)?\]'

def ptr(before,after=''):
  return '(?<={before})(0x)?[0-9a-fA-F]+(?={after})'.format(before=re.escape(before),after=re.escape(after))

def subarray_ptr(before):
  return '(?<={before} \*\()(0x)?[0-9a-fA-F]+(?=\)\[\d(:\d)?\])'.format(
    before=re.escape(before),
  )


class SubArrayPtrElem(object):
  def __init__(self,type,nstars,name):
    self.type=re.escape(type)
    self.nstars=nstars
    self.name=re.escape(name)
    self.reg_arrname=re.compile('{type} {stars} {name}{SLICE} = \[\s*'.format(
      type=self.type,
      stars=re.escape('*'*self.nstars),
      name=self.name,
      SLICE=SLICE_REGEX,
    ))
    self.reg_addr=re.compile('^'+ADDR_REGEX)
    self.reg_commaspace=re.compile(',\s*')
    self.reg_subarr={}
    for ns in range(2,nstars):
      self.reg_subarr[ns] = re.compile('^{type} {stars} \*\({ADDR}\){SLICE} = \[\s*'.format(
        type=self.type,
        stars=re.escape('*'*ns),
        ADDR=ADDR_REGEX,
        SLICE=SLICE_REGEX,
      ))
  def __call__(self,bufstr):
    coords=[]
    for l1,l2 in map(lambda x:x.span(),self.reg_arrname.finditer(bufstr)):
      #print 'arr',l1,l2
      l=l2
      found=True
      for ns in reversed(range(2,self.nstars)):
        match=self.reg_subarr[ns].search(bufstr[l:])
        if match:
          l+=match.span()[1]
          #print 'subarr',l
        else:
          #print 'break'
          found=False
          break
      if found:
        while True:
          match=self.reg_addr.search(bufstr[l:])
          if match:
            coord=match.span()
            coord=(coord[0]+l,coord[1]+l)
            #print bufstr[coord[0]:coord[1]]
            coords.append(coord)
            l=coord[1]
            match=self.reg_commaspace.search(bufstr[l:])
            if match:
              l+=match.span()[1]
            else:
              break
          else:
            break
    return coords


def subarray_ptr_elem(type,nstars,name):
  return SubArrayPtrElem(type,nstars,name)


regexes=[
]


overlay_regexes=[
  ('aux',re.escape('enter new slice N or N:M'))
]


def test():
  test_SubArrayPtrElem='\
  incompl_struct ****** is[0:2] = [                   \
    incompl_struct ***** *(0x601030)[0:2] = [         \
      incompl_struct **** *(0x601050)[0:2] = [        \
        incompl_struct *** *(0x601070)[0:2] = [       \
          incompl_struct ** *(0x601090)[0:2] = [      \
            0x6010b0,                                 \
            0x0,                                      \
            0x0,                                      \
          ]                                           \
  '
  SubArrayPtrElemObj=SubArrayPtrElem(type='incompl_struct',name='is',nstars=6)
  print SubArrayPtrElemObj(test_SubArrayPtrElem)

def ignore_frame (fr_num):
  return u'#{fr_num} [^─]+'.format(fr_num=fr_num)

if __name__=="__main__":
  test()
