import re

def ptr(before,after=''):
  return '(?<={before})(0x)?[0-9a-fA-F]+(?={after})'.format(before=re.escape(before),after=re.escape(after))

def subarray_ptr(before,after=''):
  return '(?<={before}\*\()(0x)?[0-9a-fA-F]+(?=\)\[\d(:\d)?\])'.format(
    before=re.escape(before),
  )

regexes=[
]


overlay_regexes=[
  ('aux',re.escape('enter new slice N or N:M'))
]