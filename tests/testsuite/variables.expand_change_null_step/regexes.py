import re
from regexes_common import ptr,subarray_ptr
import regexes_common

regexes=[
  ('aux',ptr('void * ptr1 = ')),
  ('aux',ptr('int *** var009_ppptr_int = ')),
  ('aux',subarray_ptr('int * ')),
  ('aux',subarray_ptr('int ** ')),
]


overlay_regexes=[
] + regexes_common.overlay_regexes
