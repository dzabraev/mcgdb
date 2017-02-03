pkgdatadir = $(datadir)/@PACKAGE@
pkgdatapythondir = $(datadir)/@PACKAGE@/python

bin_SCRIPTS = mcgdb
pkgdata_DATA = defines-mcgdb.gdb  startup.gdb
pkgdatapython_DATA = python/mcgdb.py


all: invoke-mc-makefile
install : invkoe-mc-install

invkoe-mc-install :
	make -C mc install

invoke-mc-makefile :
	make -C mc

startup.gdb :
	echo "source $(pkgdatadir)/mcgdb.py" > startup.gdb

process-mcgdb :
	sed "s#STARTUP_SCRIPT=startup.gdb#STARTUP_SCRIPT=$(pkgdatadir)/startup.gdb#"  mcgdb -i

python/mcgdb.py : process-mcgdb

python/mcgdb.py :
	cp python/mcgdb.py.in  python/mcgdb.py
	sed "s#PATH_TO_DEFINES_MCGDB=.*#PATH_TO_DEFINES_MCGDB=\"$(pkgdatadir)/defines-mcgdb.gdb\"#"  python/mcgdb.py -i
	sed "s#PATH_TO_MC=.*#PATH_TO_MC=\"@bindir@/mcgdb-mcedit\"#"  python/mcgdb.py -i


