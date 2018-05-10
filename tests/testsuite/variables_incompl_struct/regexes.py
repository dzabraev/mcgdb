import re
from regexes_common import ptr,subarray_ptr,overlay_regexes,subarray_ptr_elem


regexes=[
  ('aux',ptr('incompl_struct ****** is = ')),
  ('aux',subarray_ptr('incompl_struct *****')),
  ('aux',subarray_ptr('incompl_struct ****')),
  ('aux',subarray_ptr('incompl_struct ***')),
  ('aux',subarray_ptr('incompl_struct **')),

  ('aux',ptr('incompl_union ****** iu = ')),
  ('aux',subarray_ptr('incompl_union *****')),
  ('aux',subarray_ptr('incompl_union ****')),
  ('aux',subarray_ptr('incompl_union ***')),
  ('aux',subarray_ptr('incompl_union **')),

  ('aux',subarray_ptr_elem(type='incompl_struct',name='is',nstars=6)),
  ('aux',subarray_ptr_elem(type='incompl_union',name='iu',nstars=6)),
]

