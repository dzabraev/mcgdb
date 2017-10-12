#include <stdio.h>
#include <stdlib.h>

typedef struct incompl_struct incompl_struct;
typedef union incompl_union incompl_union;

void end_of_init(void) {}

int
main(void) {
  incompl_struct ******is=NULL;
  incompl_union  ******iu=NULL;

  is                   = (incompl_struct ******)malloc(sizeof(void *));
  is[0]                = (incompl_struct *****)malloc(sizeof(void *));
  is[0][0]             = (incompl_struct ****)malloc(sizeof(void *));
  is[0][0][0]          = (incompl_struct ***)malloc(sizeof(void *));
  is[0][0][0][0]       = (incompl_struct **)malloc(sizeof(void *));
  is[0][0][0][0][0]    = (incompl_struct *)malloc(sizeof(void *));

  iu                   = (incompl_union ******)malloc(sizeof(void *));
  iu[0]                = (incompl_union *****)malloc(sizeof(void *));
  iu[0][0]             = (incompl_union ****)malloc(sizeof(void *));
  iu[0][0][0]          = (incompl_union ***)malloc(sizeof(void *));
  iu[0][0][0][0]       = (incompl_union **)malloc(sizeof(void *));
  iu[0][0][0][0][0]    = (incompl_union *)malloc(sizeof(void *));

  end_of_init();

  is=NULL;
  is                   = (incompl_struct ******)malloc(sizeof(void *));
  is[0]=NULL;
  is[0]                = (incompl_struct *****)malloc(sizeof(void *));
  is[0][0]=NULL;
  is[0][0]             = (incompl_struct ****)malloc(sizeof(void *));
  is[0][0][0]=NULL;
  is[0][0][0]          = (incompl_struct ***)malloc(sizeof(void *));
  is[0][0][0][0]=NULL;
  is[0][0][0][0]       = (incompl_struct **)malloc(sizeof(void *));
  is[0][0][0][0][0]=NULL;
  is[0][0][0][0][0]    = (incompl_struct *)malloc(sizeof(void *));

  is=NULL;
  is                   = (incompl_struct ******)malloc(sizeof(void *));
  is[0]=NULL;
  is[0]                = (incompl_struct *****)malloc(sizeof(void *));
  is[0][0]=NULL;
  is[0][0]             = (incompl_struct ****)malloc(sizeof(void *));
  is[0][0][0]=NULL;
  is[0][0][0]          = (incompl_struct ***)malloc(sizeof(void *));
  is[0][0][0][0]=NULL;
  is[0][0][0][0]       = (incompl_struct **)malloc(sizeof(void *));
  is[0][0][0][0][0]=NULL;
  is[0][0][0][0][0]    = (incompl_struct *)malloc(sizeof(void *));

  is=NULL;
  is                   = (incompl_struct ******)malloc(sizeof(void *));
  is[0]=NULL;
  is[0]                = (incompl_struct *****)malloc(sizeof(void *));
  is[0][0]=NULL;
  is[0][0]             = (incompl_struct ****)malloc(sizeof(void *));
  is[0][0][0]=NULL;
  is[0][0][0]          = (incompl_struct ***)malloc(sizeof(void *));
  is[0][0][0][0]=NULL;
  is[0][0][0][0]       = (incompl_struct **)malloc(sizeof(void *));
  is[0][0][0][0][0]=NULL;
  is[0][0][0][0][0]    = (incompl_struct *)malloc(sizeof(void *));



  printf("%p %p\n",is,iu);
  return 0;
}