testdirs = testsuite/variables

all :
	for testdir in $(testdirs); do \
	  make -C $$testdir ; \
	done

clean :
	for testdir in $(testdirs); do \
	  make -C $$testdir clean ; \
	done

test :
	python runtest.py