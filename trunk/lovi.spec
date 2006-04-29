Name:           lovi
Version:        __VERSION__
Release:        1
Summary:        Log file monitor
Group:          Applications/System
License:        GPL
Packager:		Akos Polster <akos@pipacs.com>
URL:            http://developer.berlios.de/projects/lovi/
Source0:        http://developer.berlios.de/projects/lovi/lovi-__VERSION__.tar.gz
Requires:       PyKDE

%description
Lovi is a log file monitor for the K Desktop Environment.

%prep
%setup
%build

%install
make install DESTDIR=$RPM_BUILD_ROOT

%clean
make clean DESTDIR=$RPM_BUILD_ROOT

%files
/usr/bin/lovi
/usr/share/applications/lovi.desktop
/usr/share/icons/lovi.png

%defattr(-,root,root,-)
%doc

%changelog
