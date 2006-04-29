VERSION=0.2
RPMBASEDIR=~/rpmbuild

install:
	install -d -m 755 $(DESTDIR)/usr/bin
	install -m 755 main.py $(DESTDIR)/usr/bin/lovi
	install -m 755 -d $(DESTDIR)/usr/share/applications
	install -m 644 lovi.desktop $(DESTDIR)/usr/share/applications
	install -m 755 -d $(DESTDIR)/usr/share/icons
	install -m 644 lovi.png $(DESTDIR)/usr/share/icons/lovi.png

clean:

tar: clean
	cd ..; \
		rm -f lovi-$(VERSION); \
		ln -s lovi lovi-$(VERSION); \
		tar czf lovi/lovi-$(VERSION).tar.gz lovi-$(VERSION)/*; \
		rm -f lovi-$(VERSION)

rpm: tar lovi.spec
	mkdir -p $(RPMBASEDIR)/SOURCES $(RPMBASEDIR)/root
	mv -f lovi-$(VERSION).tar.gz $(RPMBASEDIR)/SOURCES
	rm -f sources/lovi-$(VERSION).spec
	sed 's/__VERSION__/$(VERSION)/g' lovi.spec \
	  > $(RPMBASEDIR)/SOURCES/lovi-$(VERSION).spec
	rpmbuild -ba --target noarch --buildroot $(RPMBASEDIR)/root \
		$(RPMBASEDIR)/SOURCES/lovi-$(VERSION).spec
	cd $(RPMBASEDIR)/SOURCES; \
	  rm -f lovi-$(VERSION).tar.gz lovi-$(VERSION).spec
