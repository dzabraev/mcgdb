#include <stdio.h>
#include <pthread.h>
#include <unistd.h>

int factorial(int n);

void skip(void) {}

void *
loop(void *) {
  int x=1,y=1;
  while (y) {}
  printf("%d\n",x);
  return 0;
}



void _init(void) {
  pthread_t tid;
  pthread_create(&tid,0,loop,0);
};


void init(void) {
  _init();
};

int main(void) {
  int x=0,i=0;
  init();
  for (i=0;i<10;i++) {
    x+=1;
  }
  x+=2;
  x+=3;
  x+=4;
  x+=5;
  x+=6;
  x+=7;
  x+=8;
  x+=9;
  x+=10;
  x+=11;
  printf("%d\n",x);
  x+=factorial(4);
  skip();
  skip();
  skip();
  skip();
  return 0;
}