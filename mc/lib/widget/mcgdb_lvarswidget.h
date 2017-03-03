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


typedef struct SelbarButton {
  char *text;
  gboolean selected;
  long x1;
  long x2;
} SelbarButton;

typedef struct Selbar {
  GList *buttons;
  int selected_color;
  int normal_color;
  gboolean redraw;
  long x;
  long y;
  long lines;
  long cols;
} Selbar;


typedef enum table_redraw {
  REDRAW_NONE   = 0,
  REDRAW_TAB    = 1
} redraw_t;

typedef struct {
  char **columns;
  long ncols;
  long y1;
  long y2;
  int *color; /*color of cells*/
} table_row;


typedef struct Table {
  GList *rows;
  long nrows;
  long ncols;
  long x;
  long y;
  long cols;
  long lines;
  long *colstart;
  long last_row_pos;
  int (*formula)(const struct Table * tab, int ncol);
  long row_offset;
  redraw_t redraw;
  gboolean (*row_callback)   (table_row *row, long nrow, long ncol);
  gboolean (**cell_callbacks) (table_row *row, long nrow, long ncol);
} Table;


typedef struct WTable
{
    Widget widget;
    Table * tab;
    Selbar *selbar;
    GHashTable *tables;
} WTable;

WTable *find_lvars (WDialog *h);
gboolean is_mcgdb_aux_dialog(WDialog *h);

#define WTABLE(x) ((WTable *)x)
#define TABLE(x)  ((Table *)x)
#define SELBAR_BUTTON(x) ((SelbarButton *)x)

#endif