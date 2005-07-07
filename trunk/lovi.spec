Name:           lovi
Version:        0.1
Release:        1
Summary:        Log file monitor

Group:          Applications/System
License:        GPL
Packager:		Akos Polster <akos@pipacs.com>
URL:            http://developer.berlios.de/projects/lovi/
Source0:        
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildRequires:  
Requires:       kdebindings >= 3.4.1

%description
Lovi is a log file monitor for the K Desktop Environment.


%prep
%setup -q


%build
%configure
make %{?_smp_mflags}


%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR=$RPM_BUILD_ROOT


%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%doc



%changelog
