#ifndef __MCGDB_LVARSWIDGET__
#define __MCGDB_LVARSWIDGET__

#include <ctype.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>
#include <assert.h>

#include <jansson.h>

#include "lib/global.h"
#include "src/editor/edit-impl.h"




typedef struct BlockCoord{
  int x_start;
  int y_start;
  int x1;
  int x2;
  int x_stop;
  int y_stop;
} BlockCoord;

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
  //char **columns;
  GNode **columns;
  int *offset;
  long ncols;
  long y1;
  long y2;
  int *xl;
  int *xr;
} table_row;


typedef struct WTable WTable;

#define CHUNK(node) ((node) ? ((cell_data_t *)(node->data)) : NULL)

typedef enum type_code {
  TYPE_CODE_NONE = 0,
  TYPE_CODE_PTR     ,
  TYPE_CODE_ARRAY   ,
  TYPE_CODE_STRUCT  ,
  TYPE_CODE_UNION   ,
} type_code_t;


typedef enum chunk_name {
  CHUNKNAME_NONE=0,
  CHUNKNAME_FRAME_NUM,
  CHUNKNAME_TH_GLOBAL_NUM,
  CHUNKNAME_VARNAME,
  CHUNKNAME_REGNAME,
  CHUNKNAME_VARVALUE,
  CHUNKNAME_REGVALUE,
  CHUNKNAME_FRAME_FUNC_NAME,
  CHUNKNAME_PARENTHESIS,
  CHUNKNAME_ASM_OP,
} chunk_name_t;

typedef struct celldata {
  chunk_name_t name;
  type_code_t type_code;
  char *str;
  char *proposed_text;
  GArray *coord;
  int color;
  gboolean selected;
  json_t *onclick_data;
  gboolean onclick_user_input;
  gint64 id;
} cell_data_t;

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
  int mouse_down_x;
  int mouse_down_y;
  int        active_col;
  table_row *active_row;
  WTable *wtab;
  int selected_row;
  gboolean draw_vline;
  gboolean draw_hline;
  const global_keymap_t * keymap;
  GHashTable *hnodes;
} Table;


typedef struct WTable
{
    Widget widget;
    Table * tab;
    Selbar *selbar;
    GHashTable *tables;
} WTable;



void pkg_table_package (json_t *pkg, WTable *wtab, const char *tabname);

void     wtable_update_bound (WTable *wtab);
WTable  *wtable_new (int y, int x, int height, int width);
void     wtable_add_table(WTable *wtab, const char *tabname, int ncols, const global_keymap_t * keymap);
void     wtable_set_current_table(WTable *wtab, const char *tabname);
void     wtable_set_colwidth_formula(WTable *wtab, const char *tabname, int (*formula)(const Table * tab, int ncol));
void     wtable_update_node(WTable *wtab, json_t *pkg);
void     wtable_draw(WTable *wtab);
void     wtable_do_row_visible(WTable *wtab, const char *tabname, int nrow);
Table *  wtable_get_table(WTable *wtab, const char *tabname);
/*перемотать содержимое таблицы tabname так, что бы строка с номером nrow
стала видимой*/
void     wtable_do_row_visible_json(WTable *wtab, json_t *pkg);

#define WTABLE(x) ((WTable *)x)
#define TABLE(x)  ((Table *)x)
#define SELBAR_BUTTON(x) ((SelbarButton *)x)
#define TABROW(x) ((table_row *)(((GList *)x)->data))
#endif