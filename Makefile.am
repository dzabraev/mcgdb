#https://www.gnu.org/software/autoconf/manual/autoconf-2.61/html_node/Preset-Output-Variables.html
#https://www.gnu.org/prep/standards/html_node/Directory-Variables.html

pkgdatadir = $(datadir)/@PACKAGE@
pkgdatapythondir = $(datadir)/@PACKAGE@/python

SUBDIRS = mc

bin_SCRIPTS = mcgdb
pkgdata_DATA = defines-mcgdb.gdb  startup.gdb

EXTRA_DIST = mcgdb.in startup.gdb.in


.PHONY:mcgdb-python-build
mcgdb-python-build:
	mkdir -p $(abs_builddir)/python/mcgdb
	ln -s $(srcdir)/python/mcgdb/srcwin.py $(abs_builddir)/python/mcgdb/srcwin.py
	ln -s $(srcdir)/python/mcgdb/asmwin.py $(abs_builddir)/python/mcgdb/asmwin.py
	ln -s $(srcdir)/python/mcgdb/auxwin.py $(abs_builddir)/python/mcgdb/auxwin.py
	ln -s $(srcdir)/python/mcgdb/basewin.py $(abs_builddir)/python/mcgdb/basewin.py
	ln -s $(srcdir)/python/mcgdb/commands.py $(abs_builddir)/python/mcgdb/commands.py
	ln -s $(srcdir)/python/mcgdb/common.py $(abs_builddir)/python/mcgdb/common.py
	ln -s $(srcdir)/python/mcgdb/__init__.py $(abs_builddir)/python/mcgdb/__init__.py
	sed "s#__PATH_TO_DEFINES_MCGDB__#$(abs_builddir)/defines-mcgdb.gdb#"  $(abs_builddir)/python/mcgdb/__init__.py -i
	sed "s#__PATH_TO_MC__#$(abs_builddir)/mc/src/mcgdb_mc#"               $(abs_builddir)/python/mcgdb/__init__.py -i

all : mcgdb-python-build

.PHONY:mcgdb-python-install
mcgdb-python-install:
	mkdir -p $(DESTDIR)$(pkgdatapythondir)
	cp -r $(srcdir)/python/mcgdb $(DESTDIR)$(pkgdatapythondir)
	sed "s#__PATH_TO_DEFINES_MCGDB__#$(pkgdatadir)/defines-mcgdb.gdb#"  $(pkgdatapythondir)/mcgdb/__init__.py -i
	sed "s#__PATH_TO_MC__#$(bindir)/mcgdb_mc#"                            $(pkgdatapythondir)/mcgdb/__init__.py -i


startup.gdb :
	cp $(srcdir)/startup.gdb.in $(abs_builddir)/startup.gdb
	sed 's#__MCGDB_PYTHON_PATH__#$(abs_builddir)/python#' $(abs_builddir)/startup.gdb -i

startup.gdb-install :
	cp $(srcdir)/startup.gdb.in $(DESTDIR)$(pkgdatadir)/startup.gdb
	sed 's#__MCGDB_PYTHON_PATH__#$(pkgdatapythondir)#' $(DESTDIR)$(pkgdatadir)/startup.gdb -i


mcgdb :
	cp $(srcdir)/mcgdb.in $(builddir)/mcgdb
	sed "s#__STARTUP_GDB__#$(abs_builddir)/startup.gdb#"  $(builddir)/mcgdb -i
	sed "s#__GDB__#$(GDB)#" $(builddir)/mcgdb -i
	chmod +x $(builddir)/mcgdb

mcgdb-install :
	cp $(srcdir)/mcgdb.in $(DESTDIR)$(bindir)/mcgdb
	sed "s#__STARTUP_GDB__#$(pkgdatadir)/startup.gdb#"  $(DESTDIR)$(bindir)/mcgdb -i
	sed "s#__GDB__#$(GDB)#" $(DESTDIR)$(bindir)/mcgdb -i
	chmod +x $(DESTDIR)$(bindir)/mcgdb

.PHONY : create-data-dirs
create-data-dirs :
	mkdir -p $(DESTDIR)$(pkgdatadir)


install-data-hook : create-data-dirs startup.gdb-install mcgdb-python-install mcgdb-install
