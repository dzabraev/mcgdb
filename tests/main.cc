#include <stdlib.h>
#include <stdio.h>

#include "head.h"
#include "file.h"
#include "myclass.h"
#include "testdir/file.h"
#include <pthread.h>
#include <unistd.h>

int globalvar = 1;

typedef struct incompl_struct incompl_struct;
typedef union incompl_union incompl_union;

class MyBase {
  int x;
  int y;
  public :
    MyBase (int x) {this->x=x; this->y=0;};
    MyBase (int x, int y) {this->x=x; this->y=y;};
    int value(void) {return x;};
    int value(int k) {return x*k;};
    int value(int k,int q) {return x*k*q;};
};

class MyBase2 {
  float x;
};

class MyDeriv : MyBase, MyBase2 {
  //double x;
  public:
    MyDeriv(int x) : MyBase(x) {};
    int value2(void) {return this->value();};
    union {
      int uni1;
      double uni2;
    };
    struct {
      int uni3;
      double uni4;
    };
};

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

void *f1(void *arg) {
  int y=10, x=0;
  for (;;) {
    int z=15;
    z+=y;
    x+=z;
    sleep(1);
  }
}

int f3(int x) {
  return x+1;
}

int fac(int n) {
  if (n==1)
    return 1;
  return n*fac(n-1);
}

void *fac50(void *arg) {
  sleep(5);
  fac(50);
  return NULL;
}

int main(void) {
  int arr[3][3][3];
  struct {
    const char *s;
  } test_utf8;
  test_utf8.s = "тест кодировки abdc";
  MyDeriv mm(1);
  char charbuf[4]="abc";
  {
    int block1=1;
    int block2=2;
    {
      int block3=3;
    }
  }
  unsigned char ucharbuf[4]="uns";
  const char const_charbuf[4]="def";
  const char* m_char_ptrbuf[2];
  m_char_ptrbuf[0] = "123";
  m_char_ptrbuf[1] = "456";
  incompl_struct *is;
  incompl_union *iu;
  incompl_union **is2;
  incompl_union ******is6;
  pthread_t tid[2];
  pthread_create(&tid[0],0,fac50,0);
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
  double *dblarr2 = dblarr;
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
  pthread_create(&tid[1],0,f1,0);
  x=f2(x);
  x=f3(x);
  x=f5(x);
  x=fac(50);
  printf("%p\n",is);
  printf("%p\n",iu);
  printf("%p\n",is2);
  printf("%p\n",is6);
  void *retval;
  pthread_join(tid[0],&retval);
  return x;
}