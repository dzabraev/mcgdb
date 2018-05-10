#include <stdio.h>

typedef void * const MYPTR;

int f2(void) {
  return 1;
}

int f1(void) {
  return f2 ();
}

int main(void) {
  static int x=0;
  x=f1();
  printf ("x=%d\n",x);
  return 0;
}