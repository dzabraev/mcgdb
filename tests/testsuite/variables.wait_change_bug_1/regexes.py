import re
from regexes_common import ptr
import regexes_common

regexes=[
  ('aux',ptr('int (*)[3][3] var006_aarr_int = ')),
]


overlay_regexes=[
] + regexes_common.overlay_regexes