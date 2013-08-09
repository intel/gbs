%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?python_version: %define python_version %(%{__python} -c "import sys; sys.stdout.write(sys.version[:3])")}
Name:       gbs
Summary:    The command line tools for Tizen package developers
Version:    0.17.2
Release:    1
Group:      Development/Tools
License:    GPLv2
BuildArch:  noarch
URL:        http://www.tizen.org
Source0:    %{name}_%{version}.tar.gz
Requires:   python >= 2.6
Requires:   python-pycurl
Requires:   sudo
Requires:   osc >= 0.139.0
Requires:   tizen-gbp-rpm >= 20130719
Requires:   depanneur >= 0.8
Requires:   mic >= 0.20

%if "%{?python_version}" < "2.7"
Requires:   python-argparse
%endif
%if ! 0%{?tizen_version:1}
Requires:   rpm-tizen >= 4.11.0.1.tizen20130618-tizen20130619
%endif
Requires:   %{name}-api = %{version}
Requires:   %{name}-export = %{version}

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

%package export
Summary:       GBS export module
Conflicts:     gbs < 0.15
Requires:      python
Requires:      gbs-api
Requires:      git-buildpackage-rpm

%description export
This package contains gbs export APIs, which can be used by
external software.


%prep
%setup -q -n %{name}-%{version}


%build
%{__python} setup.py build

%install
%{__python} setup.py install --prefix=%{_prefix} --root=%{buildroot}

#mkdir -p %{buildroot}/%{_prefix}/share/man/man1
#install -m644 doc/gbs.1 %{buildroot}/%{_prefix}/share/man/man1

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%doc README.rst docs/RELEASE_NOTES
#%{_mandir}/man1/*
%{python_sitelib}/gitbuildsys/cmd_*.py*
%{python_sitelib}/gitbuildsys/cmd_build.py
%{python_sitelib}/gitbuildsys/cmd_changelog.py
%{python_sitelib}/gitbuildsys/cmd_chroot.py
%{python_sitelib}/gitbuildsys/cmd_clone.py
%{python_sitelib}/gitbuildsys/cmd_createimage.py
%{python_sitelib}/gitbuildsys/cmd_import.py
%{python_sitelib}/gitbuildsys/cmd_pull.py
%{python_sitelib}/gitbuildsys/cmd_remotebuild.py
%{python_sitelib}/gitbuildsys/cmd_submit.py
%{python_sitelib}/gitbuildsys/parsing.py*
%{_bindir}/*
%{_sysconfdir}/bash_completion.d
%{_sysconfdir}/zsh_completion.d

%files api
%defattr(-,root,root,-)
%dir %{python_sitelib}/gitbuildsys
%{python_sitelib}/gitbuildsys/__init__.py*
%{python_sitelib}/gitbuildsys/oscapi.py*
%{python_sitelib}/gitbuildsys/errors.py*
%{python_sitelib}/gitbuildsys/log.py*
%{python_sitelib}/gitbuildsys/safe_url.py*
%{python_sitelib}/gitbuildsys/conf.py*
%{python_sitelib}/gitbuildsys/utils.py*
%{python_sitelib}/gbs-*-py*.egg-info

%files export
%defattr(-,root,root,-)
%{python_sitelib}/gitbuildsys/cmd_export.py*

