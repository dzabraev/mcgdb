#https://www.gnu.org/software/autoconf/manual/autoconf-2.61/html_node/Preset-Output-Variables.html
#https://www.gnu.org/prep/standards/html_node/Directory-Variables.html

pkgdatadir = $(datadir)/@PACKAGE@
pkgdatapythondir = $(datadir)/@PACKAGE@/python

SUBDIRS = mc

bin_SCRIPTS = mcgdb
pkgdata_DATA = defines-mcgdb.gdb  startup.gdb
pkgdatapython_DATA = python/mcgdb.py python/mcgdb_const.py

EXTRA_DIST = mcgdb.in

python/mcgdb_const.py:
	echo -n ''                                                          > python/mcgdb_const.py
	echo "PATH_TO_MC = '$(abs_builddir)/mc/src/mcgdb_mc'"              >> python/mcgdb_const.py
	echo "PATH_TO_DEFINES_MCGDB = '$(abs_builddir)/defines-mcgdb.gdb'" >> python/mcgdb_const.py

startup.gdb :
	echo '' > startup.gdb
	echo "source $(abs_builddir)/python/mcgdb_const.py" >> startup.gdb
	echo "source $(abs_builddir)/python/mcgdb.py"       >> startup.gdb

mcgdb :
	cp $(srcdir)/mcgdb.in $(builddir)/mcgdb
	sed "s#__STARTUP_GDB__#$(abs_builddir)/startup.gdb#"  mcgdb -i
	sed "s#__GDB__#$(GDB)#" mcgdb -i
	chmod +x mcgdb

install-exec-hook:
	sed "s#STARTUP_SCRIPT=.*#STARTUP_SCRIPT=$(pkgdatadir)/startup.gdb#"  $(DESTDIR)$(bindir)/mcgdb -i

install-data-hook:
	mkdir -p $(DESTDIR)$(pkgdatadir)
	mkdir -p $(DESTDIR)$(pkgdatapythondir)
	echo ''                                                     > $(DESTDIR)$(pkgdatadir)/startup.gdb
	echo "source $(pkgdatapythondir)/mcgdb_const.py" >> $(DESTDIR)$(pkgdatadir)/startup.gdb
	echo "source $(pkgdatapythondir)/mcgdb.py"       >> $(DESTDIR)$(pkgdatadir)/startup.gdb
	echo -n ''                                                        > $(DESTDIR)$(pkgdatapythondir)/mcgdb_const.py
	echo "PATH_TO_MC = '$(bindir)/mcgdb_mc'"               >> $(DESTDIR)$(pkgdatapythondir)/mcgdb_const.py
	echo "PATH_TO_DEFINES_MCGDB = '$(pkgdatadir)/defines-mcgdb.gdb'" >> $(DESTDIR)$(pkgdatapythondir)/mcgdb_const.py
