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
  public :
    int x;
    int y;
    MyBase (int x) {this->x=x; this->y=0;};
    MyBase (int x, int y) {this->x=x; this->y=y;};
    int value(void) {return x;};
    int value(int k) {return x*k;};
    int value(int k,int q) {return x*k*q;};
};

class MyBase2 {
  public:
    float x;
};

class MyDeriv : public MyBase, public MyBase2 {
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
  static int arr[3][3][3];
  for (int i=0;i<3;i++)
    for (int j=0;j<3;j++)
      for (int k=0;k<3; k++)
        arr[i][j][k] = i+10*j+100*k;

  for (int i=0;i<3;i++)
    for (int j=0;j<3;j++)
      for (int k=0;k<3; k++)
        arr[i][j][k] = k+10*i+100*j;


  MyDeriv mm(1);
  mm.MyBase::x=11;
  mm.MyBase::y=12;
  mm.MyBase2::x=0.5;
  mm.uni1=13;
  mm.uni3=14;

  mm.MyBase::x=12;
  mm.MyBase::y=13;
  mm.MyBase2::x=0.6;
  mm.uni1=14;
  mm.uni3=15;




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
  const char* m_char_ptrbuf[2] = {(char *)7,(char *)8};
  int x=10;
  m_char_ptrbuf[0] = "123";
  m_char_ptrbuf[1] = "456";
  incompl_struct *is;
  incompl_union *iu;
  incompl_union **is2;
  incompl_union ******is6;
  int **intarr=0;
  int ***intarr3=0;
  double *dblarr=0;
  double *dblarr2=0;
  void *retval=0;

  union {
    int x;
    double y;
  } uni;
  uni.y=0.9;


  struct mystruct darr[2];
  const char * longstr = "123456789abcdef123456789abcdef";
  int x1=1,x2=2,x3=3,x4=4,x5=5,x6=6,x7=7,x888888888888888=8888;
  MyClass mycl;

  pthread_t tid[2];
  pthread_create(&tid[0],0,fac50,0);

  is6                   = (incompl_union ******)malloc(sizeof(void *)*1);
  is6[0]=0;
  is6[0]                = (incompl_union *****)malloc(sizeof(void *)*2);
  is6[0][0]             = (incompl_union ****)malloc(sizeof(void *)*3);
  is6[0][1]             = (incompl_union ****)malloc(sizeof(void *));
  is6[0][0][0]          = (incompl_union ***)malloc(sizeof(void *)*4);
  is6[0][0][1]          = (incompl_union ***)malloc(sizeof(void *)*4);
  is6[0][0][2]          = (incompl_union ***)malloc(sizeof(void *)*4);
  is6[0][0][0][0]       = (incompl_union **)malloc(sizeof(void *)*5);
  is6[0][0][0][1]       = (incompl_union **)malloc(sizeof(void *)*5);
  is6[0][0][0][2]       = (incompl_union **)malloc(sizeof(void *)*5);
  is6[0][0][0][3]       = (incompl_union **)malloc(sizeof(void *)*5);
  is6[0][0][0][0][0]    = (incompl_union *)malloc(sizeof(void *)*6);
  is6[0][0][0][0][1]    = (incompl_union *)malloc(sizeof(void *)*6);
  is6[0][0][0][0][2]    = (incompl_union *)malloc(sizeof(void *)*6);
  is6[0][0][0][0][3]    = (incompl_union *)malloc(sizeof(void *)*6);
  is6[0][0][0][0][4]    = (incompl_union *)malloc(sizeof(void *)*6);

  intarr = (int **)malloc(10*sizeof(int *));
  intarr[0] = (int *)malloc(10*sizeof(int *));
  intarr[1] = (int *)malloc(10*sizeof(int *));
  intarr[2] = (int *)malloc(10*sizeof(int *));
  intarr[0][0]=0;
  intarr[0][1]=1;
  intarr[0][2]=2;
  intarr[1][0]=10;
  intarr[1][1]=11;
  intarr[1][2]=12;
  intarr[1][3]=13;
  intarr[2][0]=20;
  intarr[2][1]=21;
  intarr[2][2]=22;
  intarr[2][3]=23;
  intarr[2][4]=23;

  intarr3 = (int ***)malloc(10*sizeof(int **));
  for (int i=0;i<10;i++)
    intarr3[i]=(int **)i;

  dblarr = (double *) malloc(5*sizeof(double));
  for (int i=0;i<5;i++)
    dblarr[i]=0.5+i;
  dblarr2 = dblarr;

  struct mystruct *d;
  d = (struct mystruct *) malloc (sizeof(struct mystruct));
  d->my1=5;
  d->my2=2;
  d->my3=0.7;
  d->st.arr = (int *)malloc (10*sizeof(int));
  for(int i=0;i<10;i++)
    d->st.arr[i] = 2+i;
  d->st.i=4;
  d->st.s=0x0;
  d->st.s3.x=10;
  d->st.s3.y=20;

  pthread_create(&tid[1],0,f1,0);
  x=f2(x);
  x=f3(x);
  x=f5(x);
  x=fac(50);
  printf("%p\n",is);
  printf("%p\n",iu);
  printf("%p\n",is2);
  printf("%p\n",is6);

  pthread_join(tid[0],&retval);
  return x;
}