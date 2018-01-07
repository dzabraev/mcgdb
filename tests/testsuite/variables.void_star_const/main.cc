#include <stdio.h>

typedef void * const MYPTR;
typedef MYPTR * MYPTR2;

int main(void) {
  MYPTR2 ptr=0;
  printf ("p=%p\n",ptr);
  return 0;
}