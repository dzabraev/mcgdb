#include <stdio.h>

typedef void * const MYPTR;

int main(void) {
  static MYPTR ptr=0;
  printf ("p=%p\n",ptr);
  return 0;
}