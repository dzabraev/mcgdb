#coding=utf8

from regexes_common import ignore_frame

regexes=[
  ('aux','LWP=\d+ "main"'),
  ('aux',ignore_frame(0),[97]),
  ('aux',ignore_frame(1)+u'─+',[97]),
]