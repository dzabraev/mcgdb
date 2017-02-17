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

typedef enum lvars_redraw {
  REDRAW_NONE   = 0,
  REDRAW_TAB    = 1
} redraw_t;

typedef struct {
  char **columns;
  long ncols;
  long y1;
  long y2;
} lvars_row;


typedef struct lvars_tab {
  GList *rows;
  long nrows;
  long ncols;
  lvars_row *colnames;
  long x;
  long y;
  long cols;
  long lines;
  long *colstart;
  long last_row_pos;
  int (*formula)(const struct lvars_tab * tab, int ncol);
  long row_offset;
  redraw_t redraw;
} lvars_tab;


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