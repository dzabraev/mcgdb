#include <stdlib.h>
#include <stdio.h>


void end_of_init(void) {}

int main(void) {
  void *ptr1=NULL, *ptr2=NULL;
  int i=1,j=2;

  int var006_aarr_int[3][3];

  for (i=0;i<3;i++)
    for (j=0;j<3;j++)
      var006_aarr_int[i][j] = i+10*j;

  end_of_init();

  return 0;
}


