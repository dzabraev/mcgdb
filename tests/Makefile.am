testcases = variables.int \
            variables.wait_change_bug_1 \
            variables.expand_change_null_step \
            variables.incompl_struct \
            variables.void_star_const \
            srcwin.common \
            srcwin.bps


all :
	for name in $(testcases); do \
	  make -C testsuite/$$name ; \
	done

clean :
	for name in $(testcases); do \
	  make -C testsuite/$$name clean ; \
	done

test : all
	python runtest.py