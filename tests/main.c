#include "head.h"
#include "file.h"
#include "myclass.h"
#include "testdir/file.h"

int globalvar = 1;

struct mystruct {
  int my1;
  long my2;
  double my3;
  struct {
    int i;
    char *s;
    struct {
      int x;
      int y;
    } s3;
  } st;
};

int f1(int x) {
  return x+1;
}

int f3(int x) {
  return x+1;
}

int fac(int n) {
  if (n==1)
    return 1;
  return n*fac(n-1);
}

int main(void) {
  struct {
    const char *s;
  } test_utf8;
  test_utf8.s = "тест кодировки abdc";
  union {
    int x;
    double y;
  } uni;
  int x=1;
  struct mystruct d;
  struct mystruct darr[5];
  const char * longstr = "123456789abcdef123456789abcdef";
  int x1=1,x2=2,x3=3,x4=4,x5=5,x6=6,x7=7,x888888888888888=8888;
  MyClass mycl;
  x=f1(x);
  x=f2(x);
  x=f3(x);
  x=f5(x);
  x=fac(50);
  return x;
}