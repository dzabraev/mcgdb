import re
from regexes_common import ptr,subarray_ptr,overlay_regexes

regexes=[
  ('aux',ptr('void * ptr1 = ')),
  ('aux',ptr('int *** var009_ppptr_int = ')),
  ('aux',subarray_ptr('int *')),
  ('aux',subarray_ptr('int **')),
]
