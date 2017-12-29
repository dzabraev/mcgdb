SUBDIRS = filemanager man2hlp vfs viewer

if USE_INTERNAL_EDIT
SUBDIRS += editor
endif

if USE_DIFF
SUBDIRS += diffviewer
endif

if ENABLE_SUBSHELL
SUBDIRS += subshell
endif

noinst_LTLIBRARIES = libinternal.la

AM_CPPFLAGS = \
	-DSYSCONFDIR=\""$(sysconfdir)/@PACKAGE@/"\" \
	-DLIBEXECDIR=\""$(libexecdir)/@PACKAGE@/"\" \
	-DDATADIR=\""$(pkgdatadir)/"\" \
	-DLOCALEDIR=\""$(localedir)"\" \
	-DEXTHELPERSDIR=\""@EXTHELPERSDIR@/"\"

if CONS_SAVER
SUBDIRS += consaver
AM_CPPFLAGS += -DSAVERDIR=\""$(pkglibexecdir)"\"
endif

AM_CPPFLAGS += -I$(top_srcdir) $(GLIB_CFLAGS)

localedir = $(datadir)/locale
pkglibexecdir = $(libexecdir)/@PACKAGE@

bin_PROGRAMS = mcgdb_mc

if USE_INTERNAL_EDIT
EDITLIB = editor/libedit.la
endif

if USE_DIFF
DIFFLIB = diffviewer/libdiffviewer.la
endif

if ENABLE_SUBSHELL
SUBSHELLLIB = subshell/libsubshell.la
endif

libinternal_la_LIBADD = \
	filemanager/libmcfilemanager.la \
	vfs/libmc-vfs.la \
	viewer/libmcviewer.la \
	$(DIFFLIB) $(EDITLIB) $(SUBSHELLLIB)

mcgdb_mc_LDADD = \
	libinternal.la \
	$(top_builddir)/lib/libmc.la

if ENABLE_VFS_SMB
# this is a hack for linking with own samba library in simple way
mcgdb_mc_LDADD += vfs/smbfs/helpers/libsamba.a
endif

SRC_mcgdb_mc_conssaver = \
	cons.handler.c consaver/cons.saver.h

mcgdb_mc_SOURCES = \
	main.c

libinternal_la_SOURCES = \
	$(SRC_mcgdb_mc_conssaver) \
	args.c args.h \
	clipboard.c clipboard.h \
	events_init.c events_init.h \
	execute.c execute.h \
	help.c help.h \
	history.h \
	keybind-defaults.c keybind-defaults.h \
	learn.c learn.h \
	setup.c setup.h \
	textconf.c textconf.h \
	util.c util.h \
	mcgdb.c mcgdb.h \
	mcgdb-bp.c mcgdb-bp.h \
	mcgdb-bp-widget.c mcgdb-bp-widget.h

if CHARSET
    libinternal_la_SOURCES += selcodepage.c selcodepage.h
endif


if ENABLE_BACKGROUND
    libinternal_la_SOURCES += background.c background.h
endif

EXTRA_DIST = $(SRC_maintainer) $(SRC_charset)

# end of automated testing



