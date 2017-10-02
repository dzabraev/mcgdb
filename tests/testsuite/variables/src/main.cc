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

void f1(void) {

}

int main(void) {
  static int arr[3][3][3];
  for (int i=0;i<3;i++)
    for (int j=0;j<3;j++)
      for (int k=0;k<3; k++)
        arr[i][j][k] = i+10*j+100*k;

  MyDeriv mm(1);
  mm.MyBase::x=11;
  mm.MyBase::y=12;
  mm.MyBase2::x=0.5;
  mm.uni1=13;
  mm.uni3=14;

  char charbuf[4]="abc";

  unsigned char ucharbuf[4]="uns";

  const char const_charbuf[4]="def";

  const char* m_char_ptrbuf[2];
  m_char_ptrbuf[0] = "123";
  m_char_ptrbuf[1] = "456";

  int x=10;

  incompl_struct  *is1=(incompl_struct *)0x1; /*check not expandable*/
  incompl_union   *iu1=(incompl_union  *)0x2; /*check not expandable*/

  const char * longstr = "123456789abcdef123456789abcdef";
  MyClass mycl;


  /*END OF INITIALIZING VARIABLES*/



  for (int i=0;i<3;i++)
    for (int j=0;j<3;j++)
      for (int k=0;k<3; k++)
        arr[i][j][k] = k+10*i+100*j;
  //POINT_ARR_INIT_2



  mm.MyBase::x=12;
  mm.MyBase::y=13;
  mm.MyBase2::x=0.6;
  mm.uni1=14;
  mm.uni3=15;
  //POINT_MM_INIT_2




  {
    int block1=1;
    int block2=2;
    printf("%d %d\n",block1,block2);//POINT_INIT_BLOCK_1
    {
      int block3=3;
      //POINT_INIT_BLOCK_2
      block1+=block3;
      block2+=block3+1;
      printf("%d %d %d\n",block1,block2, block3);
    }
    printf("%d %d\n",block1,block2);
    //POINT_CLOSE_BLOCK_1
  }
  //POINT_CLOSE_BLOCK_2




  incompl_struct **is2; /*check expand 1 level*/
  incompl_union  **iu2; /*check expand 1 level*/

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
  //POINT_INIT_UNI_1


  struct mystruct darr[2];
  darr[0].my1=1;
  darr[0].my2=2;
  darr[0].my2=2.1;
  darr[0].st.arr=0;
  darr[0].st.i=3;
  darr[0].st.s=0x0;
  darr[0].st.s3.x=4;
  darr[0].st.s3.y=5;



  incompl_union ******is6;
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

  f1();

  /*prevent optimizing out*/
  printf("%p",is1);
  printf("%p",is2);
  printf("%p",iu1);
  printf("%p",iu2);

  return x;
}