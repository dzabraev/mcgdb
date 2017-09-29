testdirs = testsuite/variables/src testsuite/encoding/src

all :
	for testdir in $(testdirs); do \
	  make -C $$testdir ; \
	done

clean :
	for testdir in $(testdirs); do \
	  make -C $$testdir clean ; \
	done

