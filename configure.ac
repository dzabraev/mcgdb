AC_PREREQ([2.69])
AC_INIT([mcgdb], [1.2], [dzabraew@gmail.com])
AM_INIT_AUTOMAKE
AC_OUTPUT(Makefile)
AC_CONFIG_SRCDIR([tests/myclass.h])
AC_CONFIG_SRCDIR([mc])
AC_CONFIG_HEADERS([config.h])

AC_ARG_VAR(GDB, set gdb)
if test "${GDB}x" == "x" ; then
  GDB=gdb
fi

AC_CONFIG_LINKS([
  defines-mcgdb.gdb:defines-mcgdb.gdb
])
AC_CONFIG_LINKS([do_checkinstall.sh:distribution/do_checkinstall.sh], [chmod +x do_checkinstall.sh])

# Checks for programs.
AC_PROG_CXX
AC_PROG_CC

# Checks for libraries.

# Checks for header files.

# Checks for typedefs, structures, and compiler characteristics.

# Checks for library functions.

AC_CONFIG_SUBDIRS([mc])
AC_OUTPUT
