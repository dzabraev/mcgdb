#include "head.h"
#include "file.h"
#include "myclass.h"

int f1(int x) {
  return x+1;
}

int f3(int x) {
  return x+1;
}



int main(void) {
  int x=1;
  MyClass mycl;
  x=f1(x);
  x=f2(x);
  x=f3(x);
  return x;
}