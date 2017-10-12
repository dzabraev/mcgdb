import re
from regexes_common import ptr,subarray_ptr
import regexes_common

regexes=[
  ('aux',ptr('void * ptr1 = ')),
  ('aux',ptr('void * ptr2 = ')),
  ('aux',ptr('int (*)[3] var005_arr_int = ')),
  ('aux',ptr('int (*)[3][3] var006_aarr_int = ')),
  ('aux',ptr('int (*)[3][3][3] var007_aaarr_int = ')),
  ('aux',ptr('int ** var008_pptr_int = ')),
  ('aux',ptr('int * var008_ptr_int = ')),
  ('aux',ptr('int *** var009_ppptr_int = ')),
  ('aux',ptr('int * *(','')),
  ('aux',subarray_ptr('int * ')),
  ('aux',subarray_ptr('int ** ')),
  ('src','mcgdb-tm.*\d\d\d\d.txt(?=\s+\[----\])'),
]


overlay_regexes=[
] + regexes_common.overlay_regexes
