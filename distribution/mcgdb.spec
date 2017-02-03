#%define toolchain_prefix /usr/baget-tools/H-linux86
%define toolchain_prefix /usr


Summary         : Front-end midnight commander(mc) for gdb
Name            : mcgdb
Version         : 1.2
Release         : 1
License         : GPL
Vendor          : NIISI RAS
Packager        : "Maxim Dzabraev" <dzabraew@gmail.com>
Group           : Development/Debuggers
ExclusiveArch   : i386 i486 i586 i686 x86_64
ExclusiveOs     : Linux
Source          : %{name}-%{version}.tar.gz
BuildRoot       : %{_tmppath}/%{name}-%{version}-root

Requires: mc, gnome-terminal, jansson
Requires: slang >= 2.0
Requires: gdb

%description
text editor mcedit as frontend for gdb.

%prep
rm -rf --preserve-root ${RPM_BUILD_ROOT}
mkdir -p ${RPM_BUILD_ROOT}

%setup -q

%build
mkdir build
cd build
../configure --prefix=%{toolchain_prefix}
make




%install
cd build
make DESTDIR=$RPM_BUILD_ROOT install


%files
%defattr(-,root,root)
%{toolchain_prefix}/bin/mcgdb
%{toolchain_prefix}/bin/mcgdb-mcedit
%{toolchain_prefix}/share/mcgdb/defines-mcgdb.gdb
%{toolchain_prefix}/share/mcgdb/startup.gdb
%{toolchain_prefix}/share/mcgdb/mcgdb.py
%{toolchain_prefix}/share/mcgdb/mcgdb.pyc
%{toolchain_prefix}/share/mcgdb/mcgdb.pyo
%{toolchain_prefix}/bin/mcgdb-mc
%{toolchain_prefix}/bin/mcgdb-mcdiff
%{toolchain_prefix}/bin/mcgdb-mcview
%{toolchain_prefix}/etc/mcgdb/filehighlight.ini
%{toolchain_prefix}/etc/mcgdb/mc.default.keymap
%{toolchain_prefix}/etc/mcgdb/mc.emacs.keymap
%{toolchain_prefix}/etc/mcgdb/mc.ext
%{toolchain_prefix}/etc/mcgdb/mc.keymap
%{toolchain_prefix}/etc/mcgdb/mc.menu
%{toolchain_prefix}/etc/mcgdb/mcedit.menu
%{toolchain_prefix}/etc/mcgdb/mcgdb-edit.indent.rc
%{toolchain_prefix}/etc/mcgdb/sfs.ini
%{toolchain_prefix}/libexec/mcgdb/ext.d/mcgdb-archive.sh
%{toolchain_prefix}/libexec/mcgdb/ext.d/mcgdb-doc.sh
%{toolchain_prefix}/libexec/mcgdb/ext.d/mcgdb-image.sh
%{toolchain_prefix}/libexec/mcgdb/ext.d/mcgdb-misc.sh
%{toolchain_prefix}/libexec/mcgdb/ext.d/mcgdb-package.sh
%{toolchain_prefix}/libexec/mcgdb/ext.d/mcgdb-sound.sh
%{toolchain_prefix}/libexec/mcgdb/ext.d/mcgdb-text.sh
%{toolchain_prefix}/libexec/mcgdb/ext.d/mcgdb-video.sh
%{toolchain_prefix}/libexec/mcgdb/ext.d/mcgdb-web.sh
%{toolchain_prefix}/libexec/mcgdb/extfs.d/README
%{toolchain_prefix}/libexec/mcgdb/extfs.d/README.extfs
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-a+
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-apt+
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-audio
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-bpp
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-changesetfs
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-deb
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-deba
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-debd
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-dpkg+
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-gitfs+
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-hp48+
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-iso9660
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-lslR
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-mailfs
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-patchfs
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-patchsetfs
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-rpm
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-rpms+
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-s3+
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-trpm
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-u7z
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-uace
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-ualz
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-uar
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-uarc
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-uarj
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-uc1541
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-ucab
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-uha
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-ulha
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-ulib
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-urar
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-uzip
%{toolchain_prefix}/libexec/mcgdb/extfs.d/mcgdb-uzoo
%{toolchain_prefix}/libexec/mcgdb/fish/README.fish
%{toolchain_prefix}/libexec/mcgdb/fish/append
%{toolchain_prefix}/libexec/mcgdb/fish/chmod
%{toolchain_prefix}/libexec/mcgdb/fish/chown
%{toolchain_prefix}/libexec/mcgdb/fish/fexists
%{toolchain_prefix}/libexec/mcgdb/fish/get
%{toolchain_prefix}/libexec/mcgdb/fish/hardlink
%{toolchain_prefix}/libexec/mcgdb/fish/info
%{toolchain_prefix}/libexec/mcgdb/fish/ln
%{toolchain_prefix}/libexec/mcgdb/fish/ls
%{toolchain_prefix}/libexec/mcgdb/fish/mkdir
%{toolchain_prefix}/libexec/mcgdb/fish/mv
%{toolchain_prefix}/libexec/mcgdb/fish/rmdir
%{toolchain_prefix}/libexec/mcgdb/fish/send
%{toolchain_prefix}/libexec/mcgdb/fish/unlink
%{toolchain_prefix}/libexec/mcgdb/fish/utime
%{toolchain_prefix}/libexec/mcgdb/mcgdb-cons.saver
%{toolchain_prefix}/libexec/mcgdb/mcgdb-mc-wrapper.csh
%{toolchain_prefix}/libexec/mcgdb/mcgdb-mc-wrapper.sh
%{toolchain_prefix}/libexec/mcgdb/mcgdb-mc.csh
%{toolchain_prefix}/libexec/mcgdb/mcgdb-mc.sh
%{toolchain_prefix}/share/locale/az/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/be/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/bg/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/ca/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/cs/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/da/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/de/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/de_CH/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/el/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/en_GB/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/eo/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/es/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/et/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/eu/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/fa/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/fi/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/fr/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/fr_CA/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/gl/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/hr/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/hu/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/ia/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/id/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/it/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/ja/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/ka/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/kk/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/ko/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/lt/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/lv/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/mn/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/nb/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/nl/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/pl/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/pt/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/pt_BR/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/ro/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/ru/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/sk/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/sl/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/sr/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/sv/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/szl/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/ta/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/te/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/tr/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/uk/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/vi/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/wa/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/zh_CN/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/locale/zh_TW/LC_MESSAGES/mcgdb.mo
%{toolchain_prefix}/share/man/es/man1/mcgdb-mc.1.gz
%{toolchain_prefix}/share/man/hu/man1/mcgdb-mc.1.gz
%{toolchain_prefix}/share/man/it/man1/mcgdb-mc.1.gz
%{toolchain_prefix}/share/man/man1/mcgdb-mc.1.gz
%{toolchain_prefix}/share/man/man1/mcgdb-mcedit.1.gz
%{toolchain_prefix}/share/man/man1/mcgdb-mcview.1.gz
%{toolchain_prefix}/share/man/pl/man1/mcgdb-mc.1.gz
%{toolchain_prefix}/share/man/ru/man1/mcgdb-mc.1.gz
%{toolchain_prefix}/share/man/sr/man1/mcgdb-mc.1.gz
%{toolchain_prefix}/share/mcgdb/examples/macros.d/macro.0.sh
%{toolchain_prefix}/share/mcgdb/examples/macros.d/macro.1.sh
%{toolchain_prefix}/share/mcgdb/examples/macros.d/macro.3.sh
%{toolchain_prefix}/share/mcgdb/examples/macros.d/macro.4.sh
%{toolchain_prefix}/share/mcgdb/examples/macros.d/macro.5.sh
%{toolchain_prefix}/share/mcgdb/examples/macros.d/macro.6.sh
%{toolchain_prefix}/share/mcgdb/examples/macros.d/macro.7.sh
%{toolchain_prefix}/share/mcgdb/help/mc.hlp
%{toolchain_prefix}/share/mcgdb/help/mc.hlp.es
%{toolchain_prefix}/share/mcgdb/help/mc.hlp.hu
%{toolchain_prefix}/share/mcgdb/help/mc.hlp.it
%{toolchain_prefix}/share/mcgdb/help/mc.hlp.pl
%{toolchain_prefix}/share/mcgdb/help/mc.hlp.ru
%{toolchain_prefix}/share/mcgdb/help/mc.hlp.sr
%{toolchain_prefix}/share/mcgdb/hints/mc.hint
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.af
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.ar
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.az
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.be
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.bg
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.ca
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.cs
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.da
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.de
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.de_CH
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.el
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.en_GB
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.eo
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.es
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.et
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.eu
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.fa
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.fi
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.fr
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.fr_CA
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.gl
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.hr
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.hu
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.ia
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.id
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.it
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.it_IT
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.ja
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.ka
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.kk
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.ko
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.lt
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.nl
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.pl
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.pt
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.pt_BR
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.ro
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.ru
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.sk
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.sl
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.sr
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.sv
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.sv_SE
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.szl
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.te
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.tr
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.uk
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.uz
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.zh
%{toolchain_prefix}/share/mcgdb/hints/mc.hint.zh_CN
%{toolchain_prefix}/share/mcgdb/mc.charsets
%{toolchain_prefix}/share/mcgdb/mc.lib
%{toolchain_prefix}/share/mcgdb/skins/dark.ini
%{toolchain_prefix}/share/mcgdb/skins/darkfar.ini
%{toolchain_prefix}/share/mcgdb/skins/default.ini
%{toolchain_prefix}/share/mcgdb/skins/double-lines.ini
%{toolchain_prefix}/share/mcgdb/skins/featured.ini
%{toolchain_prefix}/share/mcgdb/skins/gotar.ini
%{toolchain_prefix}/share/mcgdb/skins/gray-green-purple256.ini
%{toolchain_prefix}/share/mcgdb/skins/gray-orange-blue256.ini
%{toolchain_prefix}/share/mcgdb/skins/mc46.ini
%{toolchain_prefix}/share/mcgdb/skins/modarcon16-defbg.ini
%{toolchain_prefix}/share/mcgdb/skins/modarcon16.ini
%{toolchain_prefix}/share/mcgdb/skins/modarcon16root-defbg.ini
%{toolchain_prefix}/share/mcgdb/skins/modarcon16root.ini
%{toolchain_prefix}/share/mcgdb/skins/modarin256-defbg.ini
%{toolchain_prefix}/share/mcgdb/skins/modarin256.ini
%{toolchain_prefix}/share/mcgdb/skins/modarin256root-defbg.ini
%{toolchain_prefix}/share/mcgdb/skins/modarin256root.ini
%{toolchain_prefix}/share/mcgdb/skins/nicedark.ini
%{toolchain_prefix}/share/mcgdb/skins/sand256.ini
%{toolchain_prefix}/share/mcgdb/skins/xoria256.ini
%{toolchain_prefix}/share/mcgdb/syntax/PKGBUILD.syntax
%{toolchain_prefix}/share/mcgdb/syntax/Syntax
%{toolchain_prefix}/share/mcgdb/syntax/ada95.syntax
%{toolchain_prefix}/share/mcgdb/syntax/as.syntax
%{toolchain_prefix}/share/mcgdb/syntax/aspx.syntax
%{toolchain_prefix}/share/mcgdb/syntax/assembler.syntax
%{toolchain_prefix}/share/mcgdb/syntax/awk.syntax
%{toolchain_prefix}/share/mcgdb/syntax/c.syntax
%{toolchain_prefix}/share/mcgdb/syntax/cabal.syntax
%{toolchain_prefix}/share/mcgdb/syntax/changelog.syntax
%{toolchain_prefix}/share/mcgdb/syntax/cmake.syntax
%{toolchain_prefix}/share/mcgdb/syntax/cs.syntax
%{toolchain_prefix}/share/mcgdb/syntax/css.syntax
%{toolchain_prefix}/share/mcgdb/syntax/cuda.syntax
%{toolchain_prefix}/share/mcgdb/syntax/cxx.syntax
%{toolchain_prefix}/share/mcgdb/syntax/cython.syntax
%{toolchain_prefix}/share/mcgdb/syntax/d.syntax
%{toolchain_prefix}/share/mcgdb/syntax/debian-changelog.syntax
%{toolchain_prefix}/share/mcgdb/syntax/debian-control.syntax
%{toolchain_prefix}/share/mcgdb/syntax/debian-description.syntax
%{toolchain_prefix}/share/mcgdb/syntax/debian-sources-list.syntax
%{toolchain_prefix}/share/mcgdb/syntax/diff.syntax
%{toolchain_prefix}/share/mcgdb/syntax/dlink.syntax
%{toolchain_prefix}/share/mcgdb/syntax/dos.syntax
%{toolchain_prefix}/share/mcgdb/syntax/ebuild.syntax
%{toolchain_prefix}/share/mcgdb/syntax/eiffel.syntax
%{toolchain_prefix}/share/mcgdb/syntax/erlang.syntax
%{toolchain_prefix}/share/mcgdb/syntax/f90.syntax
%{toolchain_prefix}/share/mcgdb/syntax/filehighlight.syntax
%{toolchain_prefix}/share/mcgdb/syntax/fortran.syntax
%{toolchain_prefix}/share/mcgdb/syntax/glsl.syntax
%{toolchain_prefix}/share/mcgdb/syntax/go.syntax
%{toolchain_prefix}/share/mcgdb/syntax/haskell.syntax
%{toolchain_prefix}/share/mcgdb/syntax/html.syntax
%{toolchain_prefix}/share/mcgdb/syntax/idl.syntax
%{toolchain_prefix}/share/mcgdb/syntax/ini.syntax
%{toolchain_prefix}/share/mcgdb/syntax/j.syntax
%{toolchain_prefix}/share/mcgdb/syntax/jal.syntax
%{toolchain_prefix}/share/mcgdb/syntax/java.syntax
%{toolchain_prefix}/share/mcgdb/syntax/js.syntax
%{toolchain_prefix}/share/mcgdb/syntax/latex.syntax
%{toolchain_prefix}/share/mcgdb/syntax/lisp.syntax
%{toolchain_prefix}/share/mcgdb/syntax/lkr.syntax
%{toolchain_prefix}/share/mcgdb/syntax/lsm.syntax
%{toolchain_prefix}/share/mcgdb/syntax/lua.syntax
%{toolchain_prefix}/share/mcgdb/syntax/m4.syntax
%{toolchain_prefix}/share/mcgdb/syntax/mail.syntax
%{toolchain_prefix}/share/mcgdb/syntax/makefile.syntax
%{toolchain_prefix}/share/mcgdb/syntax/ml.syntax
%{toolchain_prefix}/share/mcgdb/syntax/named.syntax
%{toolchain_prefix}/share/mcgdb/syntax/nemerle.syntax
%{toolchain_prefix}/share/mcgdb/syntax/nroff.syntax
%{toolchain_prefix}/share/mcgdb/syntax/octave.syntax
%{toolchain_prefix}/share/mcgdb/syntax/pascal.syntax
%{toolchain_prefix}/share/mcgdb/syntax/perl.syntax
%{toolchain_prefix}/share/mcgdb/syntax/php.syntax
%{toolchain_prefix}/share/mcgdb/syntax/po.syntax
%{toolchain_prefix}/share/mcgdb/syntax/povray.syntax
%{toolchain_prefix}/share/mcgdb/syntax/procmail.syntax
%{toolchain_prefix}/share/mcgdb/syntax/properties.syntax
%{toolchain_prefix}/share/mcgdb/syntax/puppet.syntax
%{toolchain_prefix}/share/mcgdb/syntax/python.syntax
%{toolchain_prefix}/share/mcgdb/syntax/ruby.syntax
%{toolchain_prefix}/share/mcgdb/syntax/sh.syntax
%{toolchain_prefix}/share/mcgdb/syntax/slang.syntax
%{toolchain_prefix}/share/mcgdb/syntax/smalltalk.syntax
%{toolchain_prefix}/share/mcgdb/syntax/spec.syntax
%{toolchain_prefix}/share/mcgdb/syntax/sql.syntax
%{toolchain_prefix}/share/mcgdb/syntax/strace.syntax
%{toolchain_prefix}/share/mcgdb/syntax/swig.syntax
%{toolchain_prefix}/share/mcgdb/syntax/syntax.syntax
%{toolchain_prefix}/share/mcgdb/syntax/tcl.syntax
%{toolchain_prefix}/share/mcgdb/syntax/texinfo.syntax
%{toolchain_prefix}/share/mcgdb/syntax/tt.syntax
%{toolchain_prefix}/share/mcgdb/syntax/unknown.syntax
%{toolchain_prefix}/share/mcgdb/syntax/verilog.syntax
%{toolchain_prefix}/share/mcgdb/syntax/vhdl.syntax
%{toolchain_prefix}/share/mcgdb/syntax/xml.syntax
%{toolchain_prefix}/share/mcgdb/syntax/yum-repo.syntax
%{toolchain_prefix}/share/mcgdb/syntax/yxx.syntax


%post

%postun

%clean
rm -rf --preserve-root $RPM_BUILD_ROOT


%changelog
* Thu Oct 20 2016 Maxim Dzabraev <dzabraew@gmail.com>
- Initial package release

