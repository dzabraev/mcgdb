testdirs = testsuite/variables.int testsuite/variables.wait_change_bug_1

all :
	for testdir in $(testdirs); do \
	  make -C $$testdir ; \
	done

clean :
	for testdir in $(testdirs); do \
	  make -C $$testdir clean ; \
	done

test : all
	python runtest.py