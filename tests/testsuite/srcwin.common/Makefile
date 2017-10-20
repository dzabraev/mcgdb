CFLAGS=-g3 -O0

all : main

src/funcs.o : src/funcs.cc
	g++ $(CFLAGS) src/funcs.cc -c -o src/funcs.o

main : src/main.cc src/funcs.o
	g++ $(CFLAGS) src/main.cc src/funcs.o -o main -lpthread

