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
	cp -asf $(abs_srcdir)/python $(abs_builddir)
	rm $(abs_builddir)/python/mcgdb/__init__.py
	cp $(abs_srcdir)/python/mcgdb/__init__.py $(abs_builddir)/python/mcgdb/__init__.py
	sed "s#__PATH_TO_DEFINES_MCGDB__#$(abs_builddir)/defines-mcgdb.gdb#"  $(abs_builddir)/python/mcgdb/__init__.py -i
	sed "s#__PATH_TO_MC__#$(abs_builddir)/mc/src/mcgdb_mc#"               $(abs_builddir)/python/mcgdb/__init__.py -i
	ln -sf $(abs_srcdir)/env.nix $(abs_builddir)/env.nix

#   tests
	cp -asf $(abs_srcdir)/tests $(abs_builddir)
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
