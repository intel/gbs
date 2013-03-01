%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?python_version: %define python_version %(%{__python} -c "import sys; sys.stdout.write(sys.version[:3])")}
Name:       gbs
Summary:    The command line tools for Tizen package developers
Version:    0.14
Release:    1
Group:      Development/Tools
License:    GPLv2
BuildArch:  noarch
URL:        http://www.tizen.org
Source0:    %{name}_%{version}.tar.gz
Requires:   python >= 2.6
Requires:   python-pycurl
Requires:   git-core
Requires:   sudo
Requires:   osc >= 0.136.0
Requires:   tizen-gbp-rpm >= 20130221
Requires:   depanneur >= 0.5
Requires:   tizen-pristine-tar >= 1.26-tizen20130122

%if "%{?python_version}" < "2.7"
Requires:   python-argparse
%endif
Requires:   librpm-tizen = 4.10.91.tizen20121215-tizen20130226

BuildRequires:  python-devel
BuildRoot:  %{_tmppath}/%{name}-%{version}-build

%description
The command line tools for Tizen package developers will
be used to do packaging related tasks. 


%prep
%setup -q -n %{name}-%{version}


%build
CFLAGS="$RPM_OPT_FLAGS" %{__python} setup.py build


%install
rm -rf $RPM_BUILD_ROOT
%if 0%{?suse_version}
%{__python} setup.py install --root=$RPM_BUILD_ROOT --prefix=%{_prefix}
%else
%{__python} setup.py install --root=$RPM_BUILD_ROOT -O1
%endif
mkdir -p %{buildroot}%{_sysconfdir}/bash_completion.d
install -pm 644 data/gbs-completion.bash %{buildroot}%{_sysconfdir}/bash_completion.d/gbs.sh

#mkdir -p %{buildroot}/%{_prefix}/share/man/man1
#install -m644 doc/gbs.1 %{buildroot}/%{_prefix}/share/man/man1

%files
%defattr(-,root,root,-)
%doc README.rst docs/RELEASE_NOTES
#%{_mandir}/man1/*
%{python_sitelib}/*
%{_bindir}/*
%{_sysconfdir}/bash_completion.d
