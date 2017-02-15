#ifndef __MCGDB_LVARSWIDGET__
#define __MCGDB_LVARSWIDGET__

#include <ctype.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

#include "lib/global.h"


int mcgdb_aux_dlg(void);


typedef struct  {
  GList *rows;
  long nrows;
  long ncols;
} lvars_tab;



typedef struct {
  char **columns;
  long ncols;
  long y1;
  long y2;
} lvars_row;


typedef struct Wlvars
{
    Widget widget;
    long lines;
    long cols;
    long x;
    long y;
    lvars_tab * tab;
} Wlvars;

Wlvars *find_lvars (WDialog *h);
gboolean is_mcgdb_aux_dialog(WDialog *h);

#endif