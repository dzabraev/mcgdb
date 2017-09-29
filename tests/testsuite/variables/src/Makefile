CFLAGS=-g3 -O0

all : main

main : main.o file.o testdir/file.o myclass.o
	g++ main.o file.o testdir/file.o myclass.o  -o main -lpthread

main.o : main.cc head.h
	g++ $(CFLAGS) main.cc -o main.o -c
file.o : file.c head.h
	g++ $(CFLAGS) file.c -o file.o -c

testdir/file.o : testdir/file.c testdir/file.h
	g++ $(CFLAGS) testdir/file.c -o testdir/file.o -c

myclass.o : myclass.cpp myclass.h
	g++ $(CFLAGS) myclass.cpp -o myclass.o -c


clean:
	rm -f *.o testdir/*.o main
