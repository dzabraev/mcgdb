#include <stdlib.h>
#include <stdio.h>

void end_of_init(void) {}

#define SZ 10

int main(void) {
  void *ptr1=NULL;
  int i=0,j=0,k=0;

  int *** var009_ppptr_int;

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

  return 0;
}


