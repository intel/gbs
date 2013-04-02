%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?python_version: %define python_version %(%{__python} -c "import sys; sys.stdout.write(sys.version[:3])")}
Name:       gbs
Summary:    The command line tools for Tizen package developers
Version:    0.15
Release:    0.rc2.<CI_CNT>.<B_CNT>
Group:      Development/Tools
License:    GPLv2
BuildArch:  noarch
URL:        http://www.tizen.org
Source0:    %{name}_%{version}.tar.gz
Requires:   python >= 2.6
Requires:   python-pycurl
Requires:   sudo
Requires:   osc >= 0.139.0
Requires:   tizen-gbp-rpm >= 20130308
Requires:   depanneur >= 0.6
Requires:   tizen-pristine-tar >= 1.26-tizen20130122

%if "%{?python_version}" < "2.7"
Requires:   python-argparse
%endif
%if ! 0%{?tizen_version:1}
Requires:   librpm-tizen >= 4.11.0.1.tizen20130304-tizen20130307
%endif
Requires:   %{name}-api = %{version}

BuildRequires:  python-devel
BuildRoot:  %{_tmppath}/%{name}-%{version}-build

%description
The command line tools for Tizen package developers will
be used to do packaging related tasks. 

%package api
Summary:       GBS APIs
Conflicts:     gbs < 0.15
Requires:      python
Requires:      python-pycurl
Requires:      osc >= 0.139.0
Requires:      git-buildpackage-rpm

%description api
This package contains gbs APIs, which can be used by
external software.

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
%{python_sitelib}/gitbuildsys/cmd_*.py*
%{python_sitelib}/gitbuildsys/conf.py*
%{python_sitelib}/gitbuildsys/parsing.py*
%{_bindir}/*
%{_sysconfdir}/bash_completion.d

%files api
%defattr(-,root,root,-)
%dir %{python_sitelib}/gitbuildsys
%{python_sitelib}/gitbuildsys/__init__.py*
%{python_sitelib}/gitbuildsys/oscapi.py*
%{python_sitelib}/gitbuildsys/errors.py*
%{python_sitelib}/gitbuildsys/log.py*
%{python_sitelib}/gitbuildsys/safe_url.py*
%{python_sitelib}/gitbuildsys/utils.py*
%{python_sitelib}/gbs-*-py*.egg-info
