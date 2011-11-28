VERSION = $(shell cat VERSION)
TAGVER = $(shell cat VERSION | sed -e "s/\([0-9\.]*\).*/\1/")

ifeq ($(VERSION), $(TAGVER))
	TAG = $(TAGVER)
else
	TAG = "HEAD"
endif

ifeq (${PREFIX}, "")
	PREFIX = "/usr/local"
endif

all:
	python setup.py build

tag:
	git tag $(VERSION)

dist-bz2:
	git archive --format=tar --prefix=tizenpkg-$(TAGVER)/ $(TAG) | \
		bzip2  > tizenpkg-$(TAGVER).tar.bz2

dist-gz:
	git archive --format=tar --prefix=tizenpkg-$(TAGVER)/ $(TAG) | \
		gzip  > tizenpkg-$(TAGVER).tar.gz

install: all install-data
	python setup.py install --prefix=${PREFIX}

dev: all
	python setup.py develop --prefix=${PREFIX}

install-data:
	install -d ${DESTDIR}/usr/share/tizenpkg/
	install -m 644 data/* ${DESTDIR}/usr/share/tizenpkg/

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
