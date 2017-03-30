#include <stdlib.h>
#include <stdio.h>

#include "head.h"
#include "file.h"
#include "myclass.h"
#include "testdir/file.h"


int globalvar = 1;

typedef struct incompl_struct incompl_struct;
typedef union incompl_union incompl_union;


struct mystruct {
  int my1;
  long my2;
  double my3;
  struct {
    int *arr;
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
  char charbuf[4]="abc";
  incompl_struct *is;
  incompl_union *iu;
  incompl_union **is2;
  incompl_union ******is6;
  is6                   = (incompl_union ******)malloc(sizeof(void *));
  is6[0]                = (incompl_union *****)malloc(sizeof(void *));
  is6[0][0]             = (incompl_union ****)malloc(sizeof(void *));
  is6[0][0][0]          = (incompl_union ***)malloc(sizeof(void *));
  is6[0][0][0][0]       = (incompl_union **)malloc(sizeof(void *));
  is6[0][0][0][0][0]    = (incompl_union *)malloc(sizeof(void *));
  //is6[0][0] = (incompl_union ****)malloc(sizeof(void *));
  int **intarr = (int **)malloc(10*sizeof(int *));
  int ***intarr3 = (int ***)malloc(10*sizeof(int **));
  intarr[0] = (int *)malloc(10*sizeof(int *));
  intarr[1] = (int *)malloc(10*sizeof(int *));
  intarr[2] = (int *)malloc(10*sizeof(int *));
  double *dblarr = (double *) malloc(5*sizeof(double));
  union {
    int x;
    double y;
  } uni;
  int x=1;
  struct mystruct *d = (struct mystruct *) malloc (sizeof(struct mystruct));
  d->my1=5;
  d->my2=1.2;
  d->st.arr = (int *)malloc (10*sizeof(int));
  struct mystruct darr[2];
  const char * longstr = "123456789abcdef123456789abcdef";
  int x1=1,x2=2,x3=3,x4=4,x5=5,x6=6,x7=7,x888888888888888=8888;
  MyClass mycl;
  x=f1(x);
  x=f2(x);
  x=f3(x);
  x=f5(x);
  x=fac(50);
  printf("%p\n",is);
  printf("%p\n",iu);
  printf("%p\n",is2);
  printf("%p\n",is6);
  return x;
}