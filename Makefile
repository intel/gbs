VERSION = $(shell cat VERSION)
TAGVER = $(shell cat VERSION | sed -e "s/\([0-9\.]*\).*/\1/")
PKGNAME = gbs

ifeq ($(VERSION), $(TAGVER))
	TAG = $(TAGVER)
else
	TAG = "HEAD"
endif

ifndef PREFIX
    PREFIX = "/usr/local"
endif

all:
	python setup.py build

tag:
	git tag $(VERSION)

dist-common: man
	git archive --format=tar --prefix=$(PKGNAME)-$(TAGVER)/ $(TAG) | tar xpf -
	git show $(TAG) --oneline | head -1 > $(PKGNAME)-$(TAGVER)/commit-id
	mkdir $(PKGNAME)-$(TAGVER)/doc; mv gbs.1 $(PKGNAME)-$(TAGVER)/doc

dist-bz2: dist-common
	tar jcpf $(PKGNAME)-$(TAGVER).tar.bz2 $(PKGNAME)-$(TAGVER)
	rm -rf $(PKGNAME)-$(TAGVER)

dist-gz: dist-common
	tar zcpf $(PKGNAME)-$(TAGVER).tar.gz $(PKGNAME)-$(TAGVER)
	rm -rf $(PKGNAME)-$(TAGVER)

man: README.rst
	rst2man $< >gbs.1

install: all
	python setup.py install --prefix=${PREFIX}

dev: all
	python setup.py develop --prefix=${PREFIX}

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
test:
	nosetests -v --with-coverage --with-xunit
