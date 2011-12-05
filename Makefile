VERSION = $(shell cat VERSION)
TAGVER = $(shell cat VERSION | sed -e "s/\([0-9\.]*\).*/\1/")

ifeq ($(VERSION), $(TAGVER))
	TAG = $(TAGVER)
else
	TAG = "HEAD"
endif

ifndef PREFIX
    PREFIX = "/usr"
endif

all:
	python setup.py build

tag:
	git tag $(VERSION)

dist-bz2:
	git archive --format=tar --prefix=tizenpkg-$(TAGVER)/ $(TAG) | \
		bzip2 > tizenpkg-$(TAGVER).tar.bz2

dist-gz:
	git archive --format=tar --prefix=tizenpkg-$(TAGVER)/ $(TAG) | \
		gzip > tizenpkg-$(TAGVER).tar.gz

install: all
	python setup.py install --prefix=${PREFIX}

dev: all
	python setup.py develop --prefix=${PREFIX}

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
