#include <stdlib.h>
#include <stdio.h>


void f1(void) {}
void f2(void) {}
void f3(void) {}

void end_of_init(void) {}

#define SZ 10

int main(void) {
  void *ptr1=NULL, *ptr2=NULL;
  int i=0,j=0,k=0;

  int var004_int=5;
  int var005_arr_int[3];
  int var006_aarr_int[3][3];
  int var007_aaarr_int[3][3][3];
  int * var008_ptr_int;
  int ** var008_pptr_int;
  int *** var009_ppptr_int;

  for (i=0;i<3;i++)
    var005_arr_int[i]=i+1;

  for (i=0;i<3;i++)
    for (j=0;j<3;j++)
      var006_aarr_int[i][j] = i+10*j;

  for (i=0;i<3;i++)
    for (j=0;j<3;j++)
      for (k=0;k<3; k++)
        var007_aaarr_int[i][j][k] = i+10*j+100*k;

  var008_ptr_int=(int *)malloc(SZ*sizeof(int));
  for (i=0;i<SZ;i++)
    var008_ptr_int[i]=i*i;

  var008_pptr_int=(int **)malloc(SZ*sizeof(int *));
  for (i=0;i<SZ;i++) {
    var008_pptr_int[i] = (int *)malloc(SZ*sizeof(int));
    for (j=0;j<SZ;j++) {
      var008_pptr_int[i][j]=10*i+j;
    }
  }

  var009_ppptr_int=(int ***)malloc(SZ*sizeof(int **));
  for (i=0;i<SZ;i++) {
    var009_ppptr_int[i] = (int **)malloc(SZ*sizeof(int *));
    for (j=0;j<SZ;j++) {
      var009_ppptr_int[i][j] = (int *)malloc(SZ*sizeof(int));
      for (k=0;k<SZ;k++) {
        var009_ppptr_int[i][j][k] = i*100+j*10+k;
      }
    }
  }

  end_of_init();


  for (i=0;i<3;i++)
    var005_arr_int[i]=i+2;

  for (i=0;i<3;i++)
    for (j=0;j<3;j++)
      var006_aarr_int[i][j] = i+10*j+1;

  for (i=0;i<3;i++)
    for (j=0;j<3;j++)
      for (k=0;k<3; k++)
        var007_aaarr_int[i][j][k] = i+10*j+100*k+1;

  for (i=0;i<SZ;i++)
    var008_ptr_int[i]=i*i+1;

  for (i=0;i<SZ;i++)
    for (j=0;j<SZ;j++)
      var008_pptr_int[i][j]=10*i+j+1;

  for (i=0;i<SZ;i++)
    for (j=0;j<SZ;j++)
      for (k=0;k<SZ;k++)
        var009_ppptr_int[i][j][k] = i*100+j*10+k+1;

  ptr1 = (void *)var009_ppptr_int;
  var009_ppptr_int=(int ***)malloc(SZ*sizeof(int **));
  for (i=0;i<SZ;i++)
    var009_ppptr_int[i]=NULL;

  for (i=0;i<SZ;i++) {
    var009_ppptr_int[i] = (int **)malloc(SZ*sizeof(int *));
    for (j=0;j<SZ;j++) {
      var009_ppptr_int[i][j]=NULL;
    }
  }

  ptr2=(void *)var009_ppptr_int;
  var009_ppptr_int=(int ***)ptr1;
  var009_ppptr_int=(int ***)ptr2;

  for (i=0;i<SZ;i++) {
    for (j=0;j<SZ;j++) {
      var009_ppptr_int[i][j]=(int *)malloc(SZ*sizeof(int));
      for (k=0;k<SZ;k++) {
        var009_ppptr_int[i][j][k]=i+j+k;
      }
    }
  }

  return 0;
}


