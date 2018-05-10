CFLAGS=-g3 -O0

all : main

funcs.o : src/funcs.cc
	g++ $(CFLAGS) src/funcs.cc -c -o funcs.o

main : src/main.cc funcs.o
	g++ $(CFLAGS) src/main.cc funcs.o -o main -lpthread

clean :
	rm -rf *.o main