#https://www.gnu.org/software/autoconf/manual/autoconf-2.61/html_node/Preset-Output-Variables.html
#https://www.gnu.org/prep/standards/html_node/Directory-Variables.html

pkgdatadir = $(datadir)/@PACKAGE@
pkgdatapythondir = $(datadir)/@PACKAGE@/python

SUBDIRS = mc

bin_SCRIPTS = mcgdb
pkgdata_DATA = defines-mcgdb.gdb  startup.gdb

EXTRA_DIST = mcgdb.in startup.gdb.in python


.PHONY:mcgdb-python-build
mcgdb-python-build:
#   python module
	mkdir -p $(abs_builddir)/python/mcgdb/
	mkdir -p $(abs_builddir)/python/mcgdb/deps
	ln -sfn $(abs_srcdir)/python/mcgdb/srcwin.py $(abs_builddir)/python/mcgdb/srcwin.py
	ln -sfn $(abs_srcdir)/python/mcgdb/asmwin.py $(abs_builddir)/python/mcgdb/asmwin.py
	ln -sfn $(abs_srcdir)/python/mcgdb/auxwin.py $(abs_builddir)/python/mcgdb/auxwin.py
	ln -sfn $(abs_srcdir)/python/mcgdb/basewin.py $(abs_builddir)/python/mcgdb/basewin.py
	ln -sfn $(abs_srcdir)/python/mcgdb/commands.py $(abs_builddir)/python/mcgdb/commands.py
	ln -sfn $(abs_srcdir)/python/mcgdb/common.py $(abs_builddir)/python/mcgdb/common.py
	ln -snf $(abs_srcdir)/python/mcgdb/valuetochunks.py $(abs_builddir)/python/mcgdb/valuetochunks.py
	ln -snf $(abs_srcdir)/python/mcgdb/gdb2.py $(abs_builddir)/python/mcgdb/gdb2.py
	ln -snf $(abs_srcdir)/python/mcgdb/deps/__init__.py $(abs_builddir)/python/mcgdb/deps/__init__.py
	ln -snf $(abs_srcdir)/python/mcgdb/deps/pysigset.py $(abs_builddir)/python/mcgdb/deps/pysigset.py
	cp      $(abs_srcdir)/python/mcgdb/__init__.py $(abs_builddir)/python/mcgdb/__init__.py
	sed "s#__PATH_TO_DEFINES_MCGDB__#$(abs_builddir)/defines-mcgdb.gdb#"  $(abs_builddir)/python/mcgdb/__init__.py -i
	sed "s#__PATH_TO_MC__#$(abs_builddir)/mc/src/mcgdb_mc#"               $(abs_builddir)/python/mcgdb/__init__.py -i
#testing file.c  file.h  file.o  head.h  main  main.c  main.o  Makefile  myclass.cpp  myclass.h  myclass.o  nframes  nframes.c  nrun.py  testdir
	mkdir -p $(abs_builddir)/tests
	mkdir -p $(abs_builddir)/tests/testcases
	ln -sfn $(abs_srcdir)/tests/Makefile        $(abs_builddir)/tests//Makefile

	mkdir -p $(abs_builddir)/tests/testcases/variables
	mkdir -p $(abs_builddir)/tests/testcases/variables/testdir
	ln -sfn $(abs_srcdir)/tests/testcases/variables/Makefile        $(abs_builddir)/tests/testcases/variables/Makefile
	ln -sfn $(abs_srcdir)/tests/testcases/variables/file.c          $(abs_builddir)/tests/testcases/variables/file.c
	ln -sfn $(abs_srcdir)/tests/testcases/variables/file.h          $(abs_builddir)/tests/testcases/variables/file.h
	ln -sfn $(abs_srcdir)/tests/testcases/variables/head.h          $(abs_builddir)/tests/testcases/variables/head.h
	ln -sfn $(abs_srcdir)/tests/testcases/variables/main.cc         $(abs_builddir)/tests/testcases/variables/main.cc
	ln -sfn $(abs_srcdir)/tests/testcases/variables/Makefile        $(abs_builddir)/tests/testcases/variables/Makefile
	ln -sfn $(abs_srcdir)/tests/testcases/variables/myclass.cpp     $(abs_builddir)/tests/testcases/variables/myclass.cpp
	ln -sfn $(abs_srcdir)/tests/testcases/variables/myclass.h       $(abs_builddir)/tests/testcases/variables/myclass.h
	ln -sfn $(abs_srcdir)/tests/testcases/variables/testdir/file.c  $(abs_builddir)/tests/testcases/variables/testdir/file.c
	ln -sfn $(abs_srcdir)/tests/testcases/variables/testdir/file.h  $(abs_builddir)/tests/testcases/variables/testdir/file.h

	mkdir -p $(abs_builddir)/tests/testcases/encoding
	ln -sfn $(abs_srcdir)/tests/testcases/encoding/Makefile         $(abs_builddir)/tests/testcases/encoding/Makefile
	ln -sfn $(abs_srcdir)/tests/testcases/encoding/encoding.cc      $(abs_builddir)/tests/testcases/encoding/encoding.cc

	make -C $(abs_builddir)/tests


	ln -sfn $(abs_srcdir)/tests/common.py $(abs_builddir)/tests/common.py
	ln -sfn $(abs_srcdir)/tests/mcgdb_record.py $(abs_builddir)/tests/mcgdb_record.py
	ln -sfn $(abs_srcdir)/tests/mcgdb_play.py $(abs_builddir)/tests/mcgdb_play.py
	ln -sfn $(abs_srcdir)/tests/iostub.py $(abs_builddir)/tests/iostub.py
	ln -sfn $(abs_srcdir)/tests/__init__.py $(abs_builddir)/tests/__init__.py
	ln -sfn $(abs_srcdir)/tests/screenshot.py $(abs_builddir)/tests/screenshot.py
	ln -sfn $(abs_srcdir)/tests/compare.py $(abs_builddir)/tests/compare.py
	chmod u+x $(abs_builddir)/tests/mcgdb_record.py
	chmod u+x $(abs_builddir)/tests/mcgdb_play.py
	chmod u+x $(abs_builddir)/tests/screenshot.py
	chmod u+x $(abs_builddir)/tests/iostub.py
	chmod u+x $(abs_builddir)/tests/compare.py

all : mcgdb-python-build

.PHONY:mcgdb-python-install
mcgdb-python-install:
	mkdir -p $(DESTDIR)$(pkgdatapythondir)
	cp -r $(abs_srcdir)/python/mcgdb $(DESTDIR)$(pkgdatapythondir)
	sed "s#__PATH_TO_DEFINES_MCGDB__#$(pkgdatadir)/defines-mcgdb.gdb#"  $(DESTDIR)$(pkgdatapythondir)/mcgdb/__init__.py -i
	sed "s#__PATH_TO_MC__#$(bindir)/mcgdb_mc#"                          $(DESTDIR)$(pkgdatapythondir)/mcgdb/__init__.py -i


startup.gdb :
	cp $(abs_srcdir)/startup.gdb.in $(abs_builddir)/startup.gdb
	sed 's#__MCGDB_PYTHON_PATH__#$(abs_builddir)/python#' $(abs_builddir)/startup.gdb -i

startup.gdb-install :
	cp $(abs_srcdir)/startup.gdb.in $(DESTDIR)$(pkgdatadir)/startup.gdb
	sed 's#__MCGDB_PYTHON_PATH__#$(pkgdatapythondir)#' $(DESTDIR)$(pkgdatadir)/startup.gdb -i


mcgdb :
	cp $(abs_srcdir)/mcgdb.in $(builddir)/mcgdb
	sed "s#__STARTUP_GDB__#$(abs_builddir)/startup.gdb#"  $(builddir)/mcgdb -i
	sed "s#__GDB__#$(GDB)#" $(builddir)/mcgdb -i
	chmod +x $(builddir)/mcgdb

mcgdb-install :
	cp $(abs_srcdir)/mcgdb.in $(DESTDIR)$(bindir)/mcgdb
	sed "s#__STARTUP_GDB__#$(pkgdatadir)/startup.gdb#"  $(DESTDIR)$(bindir)/mcgdb -i
	sed "s#__GDB__#$(GDB)#" $(DESTDIR)$(bindir)/mcgdb -i
	chmod +x $(DESTDIR)$(bindir)/mcgdb

.PHONY : create-data-dirs
create-data-dirs :
	mkdir -p $(DESTDIR)$(pkgdatadir)


install-data-hook : create-data-dirs startup.gdb-install mcgdb-python-install mcgdb-install
