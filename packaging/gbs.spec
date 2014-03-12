%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?python_version: %define python_version %(%{__python} -c "import sys; sys.stdout.write(sys.version[:3])")}
%define jobs_dir /var/lib/jenkins/jobs
%define scripts_dir /var/lib/jenkins/jenkins-scripts

Name:       gbs
Summary:    The command line tools for Tizen package developers
Version:    0.21
%if 0%{?opensuse_bs}
Release:    1.<CI_CNT>.<B_CNT>
%else
Release:    1
%endif
Group:      Development/Tools
License:    GPLv2
BuildArch:  noarch
URL:        http://www.tizen.org
Source0:    %{name}_%{version}.tar.gz
Requires:   python >= 2.6
Requires:   python-pycurl
Requires:   sudo
Requires:   osc >= 0.139.0
Requires:   tizen-gbp-rpm >= 20140306
Requires:   depanneur >= 0.12

%if "%{?python_version}" < "2.7"
Requires:   python-argparse
%endif
%if ! 0%{?tizen_version:1}
Requires:   rpm-tizen >= 4.11.0.1.tizen20130618-tizen20131001
%endif
Requires:   %{name}-api = %{version}-%{release}
Requires:   %{name}-export = %{version}-%{release}
Requires:   %{name}-remotebuild = %{version}-%{release}

BuildRequires:  python-devel
BuildRequires:  python-docutils
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
Requires:      tizen-pristine-tar >= 20131205
Requires:      gbs-api = %{version}-%{release}
Requires:      git-buildpackage-rpm

%description export
This package contains gbs export APIs, which can be used by
external software.

%package remotebuild
Summary:       GBS remotebuild module
Conflicts:     gbs < 0.18.1
Requires:      python
Requires:      gbs-api = %{version}-%{release}
Requires:      gbs-export = %{version}-%{release}
Requires:      git-buildpackage-rpm

%description remotebuild
This package contains gbs remotebuild APIs, which can be used by
external software.

%package jenkins-jobs
Summary: GBS local full build jenkins jobs configurations.

%description jenkins-jobs
These jenkins jobs are used to build tizen source from scratch or
only a part of packages, and create images finally.

%package jenkins-scripts
Summary:  Jenkins scripts used by gbs-jenkins-job
Requires: gbs
Requires: mic

%description jenkins-scripts
These scripts are used by GBS local full build jenkins jobs. These
scripts should be installed on Jenkins slave nodes.

%prep
%setup -q -n %{name}-%{version}


%build
%{__python} setup.py build
make man

%install
%{__python} setup.py install --prefix=%{_prefix} --root=%{buildroot}

mkdir -p %{buildroot}/%{_prefix}/share/man/man1
install -m644 docs/gbs.1 %{buildroot}/%{_prefix}/share/man/man1

# Install Jenkins Jobs
for job_name in $(ls jenkins-jobs/configs)
do
    mkdir -p %{buildroot}/%{jobs_dir}/${job_name}
    install -m644 jenkins-jobs/configs/${job_name}/config.xml %{buildroot}/%{jobs_dir}/${job_name}
done

#Install Jenkins Scripts
mkdir -p %{buildroot}/%{scripts_dir}
install -m755 jenkins-jobs/scripts/*  %{buildroot}/%{scripts_dir}

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%doc README.rst docs/RELEASE_NOTES
%{_mandir}/man1/*
%{python_sitelib}/gitbuildsys/cmd_build.py*
%{python_sitelib}/gitbuildsys/cmd_changelog.py*
%{python_sitelib}/gitbuildsys/cmd_chroot.py*
%{python_sitelib}/gitbuildsys/cmd_clone.py*
%{python_sitelib}/gitbuildsys/cmd_createimage.py*
%{python_sitelib}/gitbuildsys/cmd_import.py*
%{python_sitelib}/gitbuildsys/cmd_pull.py*
%{python_sitelib}/gitbuildsys/cmd_submit.py*
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

%files remotebuild
%defattr(-,root,root,-)
%{python_sitelib}/gitbuildsys/cmd_remotebuild.py*

%files jenkins-jobs
%defattr(-,jenkins,jenkins,-)
%dir /var/lib/jenkins
%dir %{jobs_dir}
%dir %{jobs_dir}/GBS-local-full-build
%dir %{jobs_dir}/GBS-local-build-with-package-list
%{jobs_dir}/GBS-local-full-build/config.xml
%{jobs_dir}/GBS-local-build-with-package-list/config.xml

%files jenkins-scripts
%defattr(-,jenkins,jenkins,-)
%dir /var/lib/jenkins
%dir %{scripts_dir}
%{scripts_dir}/job_local_full_build
%{scripts_dir}/job_build_packagelist
%{scripts_dir}/common_functions
