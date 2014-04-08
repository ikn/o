PYTHON_VERSION := 2

.PHONY: all clean distclean

all:
	echo $(PYTHON_VERSION) > py_ver
	CFLAGS="$(CFLAGS) `pkg-config --cflags sdl`" ./setup $(PYTHON_VERSION)
	@ # convert code if want Python 3
ifeq ($(PYTHON_VERSION), 3)
	./2to3
else
	./3to2
endif
	@ # Python 3 generates weirdly-named lib files
	cp -a build/lib*-$(PYTHON_VERSION).[0-9]*/*.so game/engine/gfx/_gm.so

clean:
	./3to2
	$(RM) -r build/ py_ver bak/
	find -regex 'game/engine/.*\.so' -delete

distclean: clean
	find -regex '.*\.py[co]' -delete
	find -regex '\(.*/\)?__pycache__' -delete
