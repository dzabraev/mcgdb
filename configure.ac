#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.

AC_PREREQ([2.69])
AC_INIT([mcgdb], [1.2], [dzabraew@gmail.com])
AM_INIT_AUTOMAKE
AC_OUTPUT(Makefile)
AC_CONFIG_SRCDIR([tests/myclass.h])
AC_CONFIG_HEADERS([config.h])

#m4_pattern_allow(AC_CONFIG_SUBDIR_CUSTOM)

#AC_CONFIG_LINKS([startup.gdb.in:startup.gdb.in])
AC_CONFIG_FILES([python/mcgdb.py.in:python/mcgdb.in.py])

#AC_CONFIG_FILES(mcgdb, [sed "s!STARTUP_SCRIPT=startup.gdb!STARTUP_SCRIPT=@bindir@/startup.gdb!"  mcgdb -i])
AC_CONFIG_FILES(mcgdb)

# Checks for programs.
AC_PROG_CXX
AC_PROG_CC

# Checks for libraries.

# Checks for header files.

# Checks for typedefs, structures, and compiler characteristics.

# Checks for library functions.
#extra_host_mc_configure_flags="--program-prefix=mcgdb-"
#AC_SUBST(extra_host_mc_configure_flags)
#AC_CONFIG_SUBDIR_CUSTOM([mc],[--program-prefix=mcgdb-])

AC_CONFIG_SUBDIRS([mc])
AC_OUTPUT
