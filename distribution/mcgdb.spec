#%define toolchain_prefix /usr/baget-tools/H-linux86
%define toolchain_prefix /usr


Summary         : Front-end midnight commander(mc) for gdb
Name            : mcgdb
Version         : 1.1
Release         : 1
License         : GPL
Vendor          : NIISI RAS
Packager        : "Maxim Dzabraev" <dzabraew@gmail.com>
Group           : Development/Debuggers
ExclusiveArch   : i386 i486 i586 i686 x86_64
ExclusiveOs     : Linux
Source          : %{name}-%{version}.tar.gz
BuildRoot       : %{_tmppath}/%{name}-%{version}-root

Requires: mc, gnome-terminal
Requires: gdb >= 7.12

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


%post

%postun

%clean
rm -rf --preserve-root $RPM_BUILD_ROOT


%changelog
* Thu Oct 20 2016 Maxim Dzabraev <dzabraew@gmail.com>
- Initial package release

