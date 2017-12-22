#include <stdio.h>
#include <pthread.h>
#include <unistd.h>

int factorial(int n);

void skip(void) {}
int thread_started=0;


int f (int x) {
  return x;
}

int f (int x, int y) {
  return x+y;
}

void *
loop(void *) {
  int x=1,y=1;
  thread_started=1;
  while (y) {
    x = f(x,y);
    x+=f(x);
  }
  printf("%d\n",x);
  return 0;
}


void _init(void) {
  pthread_t tid;
  pthread_create(&tid,0,loop,0);
  while (!thread_started) {sleep(0);}
};

void init(void) {
  _init();
};

int main(void) {
  int x=1;
  int y=1;
  init();

  while (y) {
    x = f(x,1);
  }

  for (x=1,y=0; x<10; x++) {
    y++;
  }

  return 0;
}