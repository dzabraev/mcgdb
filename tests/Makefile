all: main.o file.o
	gcc main.o file.o -o main

main.o : main.c head.h
	gcc -g3 -O0 main.c -o main.o -c
file.o : file.c head.h
	gcc -g3 -O0 file.c -o file.o -c