#include <config.h>
#include <assert.h>

#include <ctype.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>
#include <stdarg.h>


#include "lib/global.h"

#include "lib/widget.h"         /* Widget */
#include "lib/widget/widget-common.h"
#include "lib/widget/mouse.h"
#include "lib/widget/dialog.h"
#include "lib/tty/key.h"

#include "src/mcgdb.h"
#include "lib/widget/mcgdb_lvarswidget.h"

#include "lib/tty/tty.h"
#include "lib/skin.h"

#include "lib/util.h"

#include <jansson.h>

#define ROW_OFFSET(tab,rowcnt) (((tab)->last_row_pos)+(rowcnt))
#define TAB_BOTTOM(tab) ((tab)->y+(tab)->lines - 1)
#define TAB_TOP(tab) ((tab)->y)


#define VARS_REGS_WIDGET_X      0
#define VARS_REGS_WIDGET_Y      0
#define VARS_REGS_WIDGET_LINES  (LINES)
#define VARS_REGS_WIDGET_COLS   (COLS/2)


#define BT_TH_WIDGET_X      (COLS/2)
#define BT_TH_WIDGET_Y      0
#define BT_TH_WIDGET_LINES  (LINES)
#define BT_TH_WIDGET_COLS   (COLS-BT_TH_WIDGET_X)



static int VARS_REGS_TABLE_ID;
static int BT_TH_TABLE_ID;

int color_selected_frame;

static cb_ret_t mcgdb_aux_dialog_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);
static cb_ret_t wtable_callback           (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);
static cb_ret_t selbar_callback           (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);

static void mcgdb_aux_dialog_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event);
static void wtable_mouse_callback           (Widget * w, mouse_msg_t msg, mouse_event_t * event);
static void selbar_mouse_callback           (Widget * w, mouse_msg_t msg, mouse_event_t * event);

size_t tty_print_utf8(const char *str);
size_t charlength_utf8(const char *str);

static table_row *  table_row_alloc(long ncols);
static void         table_row_destroy(table_row *row);
static void         table_update_bounds(Table * tab, long y, long x, long lines, long cols);
static Table *      table_new (long ncols);
static int          table_add_row (Table * tab);
//static int          table_add_row_arr (Table * tab, const char **cols);
static void         table_destroy(Table *tab);
static void         table_clear_rows(Table * tab);
static void         table_draw(Table * tab);
static void         table_draw_row (Table * tab, table_row *r);
static void         table_update_colwidth(Table * tab);
static void         table_set_colwidth_formula(Table * tab, int (*formula)(const Table * tab, int ncol));
static void         table_setcolor(Table *tab, int nrow, int ncol, int color);
static void         table_process_click(Table *tab, mouse_event_t * event);
static void         table_set_cell_text(Table *tab, int nrow, int ncol, json_t *text);
static void         table_set_cell_color(Table *tab, int nrow, int ncol, const char *fg, const char *bg, const char *attrib);
static int          formula_eq_col(const Table * tab, int ncol);
static int          formula_adapt_col(const Table * tab, int ncol);
static void         wtable_update_bound(WTable *wtab);
static void         wtable_draw(WTable *wtab);

static void         table_add_offset(Table *tab, int off);
WTable  *           find_wtable (WDialog *h);

static int
print_chunks (json_t *chunk, int x1, int x2, int start_pos, int right_bound, Table *tab, int * rowcnt);

static int
print_str_chunk (json_t *chunk, int x1, int x2, int start_pos, int right_bound, Table * tab, int * rowcnt);

static int
get_chunk_horiz_shift(json_t * chunk);


gint    find_button_in_list(gconstpointer a, gconstpointer b);

Selbar *find_selbar (WDialog *h);


static  WTable  *wtable_new  (int y, int x, int height, int width);
static  Selbar *selbar_new (int y, int x, int height, int width);
void    selbar_add_button(Selbar *selbar, const char * text);
void    ghfunc_table_update_bounds(__attribute__((unused)) gpointer key, gpointer value, gpointer user_data);
static void     selbar_set_current_button(Selbar *selbar, const char *tabname);
static void     selbar_draw (Selbar *bar);
static void     reset_selected (gpointer data, gpointer user_data);
static Table *  wtable_get_table(WTable *wtab, const char *tabname);


static table_row *
TAB_LAST_ROW(Table * tab) {
  return (tab->rows) ? (table_row *)(g_list_last (tab->rows)->data) : NULL;
}

static table_row *
TAB_FIRST_ROW(Table * tab) {
  return tab->rows ? (table_row *)(tab->rows->data) : NULL;
}


static void
insert_pkg_json_into_table(json_t *json_tab, Table *tab) {
  json_t *json_rows = json_object_get (json_tab, "rows");
  json_t *colors    = json_object_get (json_tab, "color");
  size_t size_rows = json_array_size (json_rows);
  size_t size_colors = json_array_size (colors);
  long nrow;
  for (size_t i=0;i<size_rows;i++) {
    json_t * row = json_array_get (json_rows,i);
    size_t rowsize = json_array_size (row);
    assert((size_t)tab->ncols==rowsize);
    nrow = table_add_row (tab);
    for (int col=0;col<tab->ncols;col++) {
      table_set_cell_text (
        tab,nrow,col,
        json_array_get (row,col)
      );
    }
  }
  for (size_t i=0; i<size_colors; i++) {
    json_t *color = json_array_get(colors,i);
    table_set_cell_color (
      tab,
      json_integer_value (json_object_get (color,"nrow")),
      json_integer_value (json_object_get (color,"ncol")),
      json_string_value  (json_object_get (color,"fg")),
      json_string_value  (json_object_get (color,"bg")),
      json_string_value  (json_object_get (color,"attrib"))
    );
  }
}

static void
pkg_table_package(json_t *pkg, WTable *wtab, const char *tabname) {
  /* Данная функция предназначена для обработки
   * табличных пакетов. Функция вставляет данные из пакета "table_data"
   * в таблицу tabname
   */
  Table *tab = wtable_get_table(wtab,tabname);
  table_clear_rows(tab);
  insert_pkg_json_into_table (json_object_get(pkg,"table"), tab);
}

static void
mcgdb_aux_dialog_gdbevt (WDialog *h) {
  WTable *wtab;
  struct gdb_action * act = event_from_gdb;
  json_t *pkg = act->pkg;
  event_from_gdb=NULL;

  switch(act->command) {
    case MCGDB_LOCALVARS:
      wtab = (WTable *)dlg_find_by_id(h, VARS_REGS_TABLE_ID);
      pkg_table_package (pkg,wtab,"localvars");
      break;
    case MCGDB_REGISTERS:
      wtab = (WTable *) dlg_find_by_id (h, VARS_REGS_TABLE_ID);
      pkg_table_package (pkg,wtab,"registers");
      break;
    case MCGDB_BACKTRACE:
      wtab = (WTable *)dlg_find_by_id(h, BT_TH_TABLE_ID);
      pkg_table_package (pkg,wtab,"backtrace");
      break;
    case MCGDB_THREADS:
      wtab = (WTable *)dlg_find_by_id(h, BT_TH_TABLE_ID);
      pkg_table_package (pkg,wtab,"threads");
      break;

    default:
      break;
  }

  free_gdb_evt (act);

}


gboolean
is_mcgdb_aux_dialog(WDialog *h) {
  return h->widget.callback==mcgdb_aux_dialog_callback;
}

static cb_ret_t
mcgdb_aux_dialog_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  WDialog *h = DIALOG (w);
  WTable  *vars_regs_table, *bt_th_table;
  switch (msg) {
    case MSG_KEY:
      {
          cb_ret_t ret = MSG_NOT_HANDLED;

          if (parm==EV_GDB_MESSAGE)
          {
            mcgdb_aux_dialog_gdbevt (h);
            ret = MSG_HANDLED;
          }
          return ret;
      }
    case MSG_DRAW:
      {
        return MSG_HANDLED;
      }
    case MSG_RESIZE:
      {
        w->lines = LINES;
        w->cols = COLS;
        vars_regs_table = (WTable *) dlg_find_by_id(h, VARS_REGS_TABLE_ID);
        WIDGET(vars_regs_table)->x      =VARS_REGS_WIDGET_X;
        WIDGET(vars_regs_table)->y      =VARS_REGS_WIDGET_Y;
        WIDGET(vars_regs_table)->lines  =VARS_REGS_WIDGET_LINES;
        WIDGET(vars_regs_table)->cols   =VARS_REGS_WIDGET_COLS;
        wtable_update_bound(vars_regs_table);

        bt_th_table = (WTable *) dlg_find_by_id(h, BT_TH_TABLE_ID);
        WIDGET(bt_th_table)->x      =   BT_TH_WIDGET_X;
        WIDGET(bt_th_table)->y      =   BT_TH_WIDGET_Y;
        WIDGET(bt_th_table)->lines  =   BT_TH_WIDGET_LINES;
        WIDGET(bt_th_table)->cols   =   BT_TH_WIDGET_COLS;
        wtable_update_bound(bt_th_table);


        return MSG_HANDLED;
      }
    case MSG_INIT:
      break;
    default:
      {
        return dlg_default_callback (w, sender, msg, parm, data);
      }
  }
  return MSG_HANDLED;
}


static void
mcgdb_aux_dialog_mouse_callback (__attribute__((unused)) Widget *  w, 
    __attribute__((unused)) mouse_msg_t msg, mouse_event_t * event) {
  gboolean unhandled = TRUE;
  event->result.abort = unhandled;
}

void
ghfunc_table_update_bounds(__attribute__((unused)) gpointer key, gpointer value, gpointer user_data) {
  WTable * wtab = WTABLE(user_data);
  Widget * w = WIDGET(wtab);
  Table  * tab  = TABLE(value);
  table_update_bounds(tab, w->y+2,w->x+1,w->lines-3,w->cols-2);
}

static void
wtable_update_bound(WTable *wtab) {
  Selbar *selbar = wtab->selbar;
  g_hash_table_foreach (wtab->tables, ghfunc_table_update_bounds, wtab);
  selbar->x     = WIDGET(wtab)->x;
  selbar->y     = WIDGET(wtab)->y;
  selbar->cols  = WIDGET(wtab)->cols;
  selbar->lines = 1;
}

static WTable *
wtable_new (int y, int x, int height, int width)
{
    WTable *wtab;
    Widget *w;

    if (height <= 0)
        height = 1;

    wtab = g_new0 (WTable, 1);
    w = WIDGET (wtab);
    widget_init (w, y, x, height, width, wtable_callback, wtable_mouse_callback);
    w->options |=   WOP_SELECTABLE;
    wtab->tables = g_hash_table_new (g_str_hash,  g_str_equal );
    wtab->selbar = selbar_new (y,x,1,width);
    return wtab;
}

static void
wtable_add_table(WTable *wtab, const char *tabname, int ncols) {
  Table *tab;
  tab = table_new(ncols);
  table_set_colwidth_formula(tab, formula_adapt_col);
  g_hash_table_insert ( wtab->tables, (gpointer) tabname, (gpointer) tab);
  selbar_add_button   ( wtab->selbar, tabname);
}

static void
wtable_set_current_table(WTable *wtab, const char *tabname) {
  wtab->tab = g_hash_table_lookup (wtab->tables, tabname);
  assert(wtab->tab!=NULL);
  selbar_set_current_button(wtab->selbar,tabname);
}

static Table *
wtable_get_table(WTable *wtab, const char *tabname) {
  return g_hash_table_lookup (wtab->tables, tabname);
}


static table_row *
table_row_alloc(long ncols) {
  table_row * row = g_new0 (table_row,1);
  row->ncols=ncols;
  row->columns = (json_t **)g_new0(json_t *, ncols);
  row->color   = (int *)g_new(int, ncols);
  for (int col=0;col<ncols;col++) {
    row->columns[col] = NULL;
    row->color[col]=EDITOR_NORMAL_COLOR;
  }
  return row;
}

static void
table_set_cell_text (Table *tab, int nrow, int ncol, json_t *text) {
  table_row *row = g_list_nth_data(tab->rows,nrow);
  json_incref (text);
  assert(row);
  assert(row->ncols > ncol);
  if (row->columns[ncol])
    json_decref (row->columns[ncol]);
  row->columns[ncol] = text;
}

static void
table_set_cell_color(Table *tab, int nrow, int ncol, const char *fg, const char *bg, const char *attrib) {
  ((table_row * )g_list_nth_data(tab->rows,nrow))->color[ncol] =
    tty_try_alloc_color_pair2 (fg, bg, attrib, FALSE);
}


/*
static table_row *
table_row_alloc_arr(long ncols, const char ** colval) {
  table_row * row = g_new0 (table_row,1);
  row->ncols=ncols;
  row->columns = (char **)g_new0(char *, ncols);
  row->color   = (int *)g_new(int, ncols);
  for (int col=0;col<ncols;col++) {
    row->columns[col] = strdup(colval[col]);
    row->color[col]=EDITOR_NORMAL_COLOR;
  }
  return row;
}*/

static void
table_process_click(Table *tab, mouse_event_t * event) {
  long line = event->y;
  GList *grow = tab->rows;
  long nrow=0,ncol;
  table_row * row;
  gboolean handled=FALSE;
  if (  (event->y < tab->y) ||
        (event->y >= tab->y+tab->lines) ||
        (event->x < tab->x) ||
        (event->x >= tab->x+tab->cols)
     ) { /*click out of table*/
     return;
  }
  while(grow) {
    row = grow->data;
    if (row->y1<=line && row->y2>=line) {
      break;
    }
    nrow++;
    grow=grow->next;
  }
  if (!grow)
    return;
  for (ncol=0;ncol<tab->ncols;ncol++) {
    if (tab->colstart[ncol]<=event->x && tab->colstart[ncol+1]>event->x) {
      break;
    }
  }
  /*`nrow` есть номер строки таблицы, по которой был сделан клик.
   *`ncol` есть номер столбца таблицы по которому был сделан клик.
  */
  assert (ncol<tab->ncols);
  if (tab->row_callback) {
    handled = tab->row_callback(row,nrow,ncol);
    if (handled)
      return;
  }
  if (tab->cell_callbacks)
    handled = tab->cell_callbacks[ncol](row,nrow,ncol);
}


static void
table_row_setcolor(table_row *row, int col, int color) {
  assert(col<row->ncols);
  row->color[col]=color;
}

static void
table_row_destroy(table_row *row) {
  for (int col=0;col<row->ncols;col++) {
    free(row->columns[col]);
  }
  g_free(row);
}

static void
table_row_destroy_g(gpointer data) {
  table_row_destroy ((table_row *)data);
}


static void
table_clear_rows(Table * tab) {
  g_list_free_full (tab->rows,table_row_destroy_g);
  tab->rows = NULL;
  tab->nrows=0;
}


static int
formula_eq_col(const Table * tab, __attribute__((unused)) int ncol) {
  return (tab->cols/tab->ncols);
}


static size_t
get_jsonstr_len_utf(json_t * chunks) {
  /*вычисляет максимальную ширину строки (array of chunks)*/
  json_t * child_chunks;
  size_t str_size = 0, max_str_size=0;
  for (size_t nchunk=0;nchunk<json_array_size(chunks); nchunk++) {
    json_t * chunk = json_array_get (chunks,nchunk);
    str_size=0;
    if (json_object_get (chunk,"str")) {
      const char * chunk_str = json_string_value (json_object_get (chunk, "str"));
      while (*chunk_str) {
        chunk_str += charlength_utf8 (chunk_str);
        str_size+=1;
      }
    }
    else if ((child_chunks = json_object_get (chunk,"chunks"))) {
      str_size = get_jsonstr_len_utf (child_chunks);
      str_size += get_chunk_horiz_shift (chunk);
    }
    if (max_str_size > str_size)
      max_str_size = str_size;
  }
  return max_str_size;
}

static int
formula_adapt_col(const Table * tab, int ncol) {
  int ncols = tab->ncols;
  int width=0,max_width=0;
  int max_avail_width = formula_eq_col(tab,ncol);
  if(ncol<ncols) {
    GList * row = tab->rows;
    for(;row;row=g_list_next(row)) {
      width = get_jsonstr_len_utf (((table_row *)row->data)->columns[ncol]);
      if (width >= max_avail_width)
        return max_avail_width;
      if (width > max_width)
        max_width=width;
    }
    return max_width>0?max_width+1:max_avail_width;
  }
  else {
    if (ncols<=1)
      return tab->cols;
    else
      return tab->cols - tab->colstart[ncol-1];
  }
}




static void
table_set_colwidth_formula(Table * tab, int (*formula)(const Table * tab, int ncol)) {
  tab->formula = formula;
}

static void
set_color_by_chunkname (json_t *chunk) {
  const char *name = json_string_value (json_object_get (chunk,"name"));
  int color = EDITOR_NORMAL_COLOR;
  if (name) {
    if (!strcmp(name,"frame_num") || !strcmp(name,"th_global_num")) {
      json_t *selected = json_object_get (chunk,"selected");
      if (selected && json_boolean_value(selected))
        color = tty_try_alloc_color_pair2 ("red", "black", "bold", FALSE);
    }
    else if (!strcmp(name,"varname") || !strcmp(name,"regname")) {
        color = tty_try_alloc_color_pair2 ("yellow", "blue", NULL, FALSE);
    }
    else if (!strcmp(name,"varvalue") || !strcmp(name,"regvalue")) {
        color = tty_try_alloc_color_pair2 ("green", "blue", NULL, FALSE);
    }
    else if (!strcmp(name,"frame_func_name")) {
        color = tty_try_alloc_color_pair2 ("cyan", "blue", NULL, FALSE);
    }
//   else if (
//        !strcmp(name,"frame_filename") ||
//        !strcmp(name,"frame_line") ||
//        !strcmp(name,"frame_fileline_delimiter")
//       ) {
//        color = tty_try_alloc_color_pair2 ("brown", "blue", NULL, FALSE);
//    }

  }
  tty_setcolor(color);
}

static void
tty_setalloc_color (const char *fg, const char *bg, const char * attr, gboolean x) {
  int color = tty_try_alloc_color_pair2 (fg, bg, attr, x);
  tty_setcolor(color);
}

static int
print_str_chunk(json_t *chunk, int x1, int x2, int start_pos, int right_bound, Table * tab, int * rowcnt) {
  const char * p;
  int offset;
  int colcnt=start_pos;
  p = json_string_value (json_object_get (chunk,"str"));
  if (!p)
    p="???";
  offset=ROW_OFFSET(tab,rowcnt[0]);
  tty_gotoyx(offset,start_pos);
  for(;;colcnt++) {
    if(colcnt>=x2) {
      /*допечатали до правой границы столбца таблицы
       *делаем перенос строки.*/
      rowcnt[0]++;
      offset=ROW_OFFSET(tab,rowcnt[0]);
      if (offset>=TAB_TOP(tab) && offset<=TAB_BOTTOM(tab))
        tty_gotoyx(offset,x1);
      colcnt=x1;
    }
    if (!*p)
      break;
    switch(*p) {
    case '\n':
      p++;
      if (colcnt!=x1)
        colcnt=x2;
      break;
    default:
      offset=ROW_OFFSET(tab,rowcnt[0]);
      if (offset>=TAB_TOP(tab) && offset<=TAB_BOTTOM(tab) && colcnt<right_bound) {
        set_color_by_chunkname (chunk);
        p+=tty_print_utf8(p);
      }
      else {
        tty_gotoyx(offset,right_bound);
        tty_setalloc_color ("brown", "blue", NULL, FALSE);
        tty_print_char('>'); /*print on widget frame*/
        p+=charlength_utf8(p);
      }
    }
  }
  return colcnt;
}

static int
get_chunk_horiz_shift(json_t * chunk) {
  int horiz_shift=0;
  json_t * type = json_object_get (chunk,"type");
  if (type) {
    const char * strval = json_string_value (type);
    if (!strcmp(strval,"struct")) {
      horiz_shift=2;
    }
  }
  return horiz_shift;
}

static int
print_chunks(json_t * chunks, int x1, int x2, int start_pos, int right_bound, Table *tab, int * rowcnt) {
  json_t * child_chunks, * type;
  for (size_t nchunk=0;nchunk<json_array_size(chunks); nchunk++) {
    json_t * chunk = json_array_get (chunks,nchunk);
    if (json_object_get (chunk,"str")) {
      start_pos = print_str_chunk (chunk,x1,x2,start_pos,right_bound,tab,rowcnt);
    }
    else if ((child_chunks = json_object_get (chunk,"chunks"))) {
      int horiz_shift = get_chunk_horiz_shift (chunk);
      if ((type=json_object_get(chunk,"type")) && !strcmp(json_string_value(type),"struct")) {
        int start_pos_chunks=x1 + horiz_shift;
        print_chunks (child_chunks,x1+horiz_shift,x2+horiz_shift,start_pos_chunks,right_bound,tab,rowcnt);
        start_pos=x1;
      }
      else {
        start_pos = print_chunks (child_chunks,x1+horiz_shift,x2+horiz_shift,start_pos,right_bound,tab,rowcnt);
      }
    }
  }
  return start_pos;
}

static void
table_draw_row (Table * tab, table_row *row) {
  long * colstart = tab->colstart;
  json_t ** columns = row->columns;
  json_t * column;
  int rowcnt;
  long max_rowcnt=1, x1, x2;
  long offset;
  row->y1 = ROW_OFFSET(tab,0);
  for(int i=0;i<tab->ncols;i++) {
    tty_setcolor(row->color[i]); /*цвет ячейки*/
    column = columns[i];
    x1 = i==0?colstart[i]:colstart[i]+1;
    x2 = colstart[i+1];
    rowcnt=0;
    offset=ROW_OFFSET(tab,rowcnt);
    if (offset>=TAB_TOP(tab) && offset<=TAB_BOTTOM(tab))
      tty_gotoyx(offset,x1);
    print_chunks (column, x1, x2, x1, x2, tab, &rowcnt);
    rowcnt++;
    if(rowcnt>max_rowcnt)
      max_rowcnt=rowcnt;
  }
  tab->last_row_pos += max_rowcnt;
  row->y2 = ROW_OFFSET(tab,0);
}



static void
table_draw(Table * tab) {
  GList *row = tab->rows;
  table_row *r;
  long offset;
  tty_fill_region(tab->y,tab->x,tab->lines,tab->cols,' ');
  tab->last_row_pos = tab->y - tab->row_offset;

  while(row) {
    r = (table_row *)row->data;
    tty_setcolor(EDITOR_NORMAL_COLOR);
    table_draw_row (tab,r);
    offset=ROW_OFFSET(tab,0);
    if (offset>TAB_TOP(tab) && offset<=TAB_BOTTOM(tab)) {
      tty_setcolor(EDITOR_NORMAL_COLOR);
      tty_draw_hline(offset,tab->x,mc_tty_frm[MC_TTY_FRM_HORIZ],tab->cols);
    }
    tab->last_row_pos++;
    /*Делаем проход до самой последней строки что бы
     * вычислить координаты начала и конца каждой строки*/
    row = g_list_next (row);
  }
  tty_setcolor(EDITOR_NORMAL_COLOR);
  for(int i=1;i<tab->ncols;i++) {
    tty_draw_vline(tab->y,tab->colstart[i],mc_tty_frm[MC_TTY_FRM_VERT],tab->lines);
  }
}

static void
table_update_colwidth(Table * tab) {
  long x        = tab->x;
  long ncols    = tab->ncols;
  long cols     = tab->cols;
  tab->colstart[0] = x;
  for(int i=0;i<ncols;i++) {
    tab->colstart[i+1] = tab->colstart[i] + tab->formula(tab,i);
  }
  tab->colstart[ncols] = x + cols;
}

static void
table_setcolor(Table *tab, int nrow, int ncol, int color) {
  table_row *row = (table_row *) g_list_nth_data (tab->rows, nrow);
  assert(row!=NULL);
  table_row_setcolor(row, ncol, color);
}

static void
table_update_bounds(Table * tab, long y, long x, long lines, long cols) {
  tab->x = x;
  tab->y = y;
  tab->lines = lines;
  tab->cols  = cols;
  tab->colstart[0] = x;
  table_update_colwidth(tab);
}


static Table *
table_new (long ncols) {
  Table *tab;
  tab = g_new0(Table,1);
  tab->ncols=ncols;
  tab->nrows=0;
  tab->colstart = (long *)g_new0(long,ncols+1);
  tab->row_offset=0;
  table_set_colwidth_formula(tab,formula_adapt_col);
  return tab;
}

static void
table_destroy(Table *tab) {
  g_free(tab->colstart);
  table_clear_rows(tab);
  g_free(tab);
}



static int
_table_insert_row(Table * tab, table_row * row) {
  tab->rows = g_list_append (tab->rows, row);
  return tab->nrows++;
}

static int
table_add_row (Table * tab) {
  long ncols = tab->ncols;
  table_row *row;
  int rc;
  row = table_row_alloc (ncols);
  rc = _table_insert_row (tab,row);
  return rc;
}

/*
static int
table_add_row_arr (Table * tab, const char **cols) {
 table_row *row = table_row_alloc_arr (tab->ncols,cols);
 return _table_insert_row (tab,row);
}*/


static void
table_add_offset(Table *tab, int off) {
  int max_offset;
  int old_offset = tab->row_offset;
  if ( !TAB_FIRST_ROW(tab) ) {
    /*empty table*/
    return;
  }
  max_offset = MAX(0,((TAB_LAST_ROW(tab)->y2 - TAB_FIRST_ROW(tab)->y1) - (TAB_BOTTOM(tab)-TAB_TOP(tab))));
  tab->row_offset += off;
  tab->row_offset = MAX(tab->row_offset, 0);
  tab->row_offset = MIN(tab->row_offset, max_offset);
  if (tab->row_offset!=old_offset)
    tab->redraw |= REDRAW_TAB;
}

static cb_ret_t
wtable_callback (Widget * w, __attribute__((unused)) Widget * sender, widget_msg_t msg, int parm, __attribute__((unused)) void *data) {
  cb_ret_t handled = MSG_HANDLED;
  WTable *wtab = (WTable *)w;
  switch(msg) {
    case MSG_DRAW:
      tty_setcolor(EDITOR_NORMAL_COLOR);
      wtab->tab->redraw |= REDRAW_TAB;
      break;
    case MSG_KEY:
      switch (parm) {
        case KEY_UP:
          table_add_offset(wtab->tab,-1);
          break;
        case KEY_DOWN:
          table_add_offset(wtab->tab,1);
          break;
        case KEY_PPAGE:
          /*Page Up*/
          /*Либо перемещаемся на треть таблицы к первой строке,
           * а если это смещение будет сильно большое, то сдвигаемся
           * на столько, что бы верхушка верхней строки была видна в верху таблицы*/
          table_add_offset(wtab->tab,-wtab->tab->lines/3);
          break;
        case KEY_NPAGE:
          /*Page Down*/
          table_add_offset(wtab->tab,wtab->tab->lines/3);
          break;
        default:
          break;
      }
      break;
    default:
      break;
  }
  if (wtab->tab->redraw & REDRAW_TAB) {
    wtable_draw(wtab);
  }
  widget_move (w, LINES, COLS);
  return handled;
}

static void
wtable_draw(WTable *wtab) {
  tty_draw_box (WIDGET(wtab)->y+1, WIDGET(wtab)->x, WIDGET(wtab)->lines-1, WIDGET(wtab)->cols, FALSE);
  table_draw (wtab->tab);
  tty_setcolor(EDITOR_NORMAL_COLOR);
  selbar_draw (wtab->selbar);
  wtab->tab->redraw = REDRAW_NONE;
}

static void
wtable_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
  WTable *wtab = (WTable *)w;

  widget_select (w);

  if (event->y==0) {
    selbar_mouse_callback (w, msg, event);
    return;
  }

  switch (msg) {
    case MSG_MOUSE_SCROLL_UP:
      table_add_offset(wtab->tab, -2);
      break;
    case MSG_MOUSE_SCROLL_DOWN:
      table_add_offset(wtab->tab, 2);
      break;
    case MSG_MOUSE_CLICK:
      table_process_click(wtab->tab, event);
      break;
    default:
      break;
  }

  if (wtab->tab->redraw & REDRAW_TAB) {
    wtable_draw (wtab);
  }
  tty_gotoyx(LINES, COLS);
}



WTable *
find_wtable (WDialog *h) {
  return (WTable *) find_widget_type(h, wtable_callback);
}

Selbar *
find_selbar (WDialog *h) {
  return (Selbar *) find_widget_type (h, selbar_callback);
}

/////////////////////////////////////////////////////////////

static void
selbar_set_current_button(Selbar *selbar, const char *tabname) {
  GList *button = selbar->buttons;
  g_list_foreach (selbar->buttons, reset_selected, NULL);
  while (button) {
    SelbarButton * btn = SELBAR_BUTTON(button->data);
    if( !strcmp(btn->text,tabname) ) {
      btn->selected=TRUE;
      return;
    }
    button = button->next;
  }
}

static void
selbar_draw (Selbar *bar) {
  GList * button = bar->buttons;
  long x=bar->x,y=bar->y,cols=bar->cols,lines=bar->lines;
  int cnt=0;
  bar->redraw=FALSE;
  tty_setcolor(EDITOR_NORMAL_COLOR);
  tty_fill_region(y,x,lines,cols,' ');
  tty_gotoyx(y,x);
  cnt++;
  tty_print_char(' ');
  while(button) {
    const char *p;
    SelbarButton * btn = ((SelbarButton *)(button->data));
    btn->x1 = cnt;
    if (btn->selected)
      tty_setcolor(bar->selected_color);
    else
      tty_setcolor(bar->normal_color);
    p = btn->text;
    if (cnt > cols)
      break;
    while(*p) {
      tty_print_char(*p++);
      if (++cnt>=cols)
        break;
    }
    btn->x2 = cnt;
    if (cnt<cols) {
      cnt++;
      tty_setcolor(EDITOR_NORMAL_COLOR);
      tty_print_char(' ');
    }
    else {
      break;
    }
    button = g_list_next(button);
  }
  tty_gotoyx(LINES,COLS);
  return;
}

static cb_ret_t
selbar_callback (Widget * w,
    __attribute__((unused)) Widget * sender,
                            widget_msg_t msg,
    __attribute__((unused)) int parm,
    __attribute__((unused)) void *data) {
  Selbar *bar = (Selbar *)w;
  switch (msg) {
    case MSG_DRAW:
      selbar_draw (bar);
      break;
    default:
      break;
  }
  return MSG_HANDLED;
}

gint
find_button_in_list(gconstpointer a, gconstpointer b) {
  SelbarButton *btn = (SelbarButton *)a;
  int x_click = ((int *)b)[0];
  if ((btn->x1 <= x_click) && (btn->x2 > x_click)) {
    return 0;
  }
  else {
    return 1;
  }
}


static void
reset_selected (gpointer data, __attribute__((unused)) gpointer user_data) {
  SELBAR_BUTTON(data)->selected=FALSE;
}

static void
selbar_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
  int click_x;
  WTable *wtab = WTABLE(w);
  Selbar *selbar = wtab->selbar;
  GList * button;
  switch (msg) {
    case MSG_MOUSE_CLICK:
      click_x = event->x;
      button = g_list_find_custom ( selbar->buttons, &click_x, find_button_in_list );
      if (button) {
        SelbarButton *btn = SELBAR_BUTTON(button->data);
        wtable_set_current_table(wtab,btn->text);
        selbar->redraw = TRUE;
      }
      break;
    default:
      break;
  }
  if (selbar->redraw)
    wtable_draw (wtab);
}


static Selbar *
selbar_new (int y, int x, int height, int width) {
    Selbar *selbar;

    if (height <= 0)
        height = 1;

    selbar = g_new0 (Selbar, 1);
    selbar->buttons=NULL;
    selbar->selected_color = tty_try_alloc_color_pair2 ("red", "black", "bold", FALSE);
    selbar->normal_color = tty_try_alloc_color_pair2 ("white", "cyan",   NULL, FALSE);
    selbar->x=x;
    selbar->y=y;
    selbar->lines=height;
    selbar->cols=width;
    return selbar;

}


void selbar_add_button(Selbar *selbar, const char * text) {
  SelbarButton *btn = g_new0 (SelbarButton,1);
  btn->text = strdup (text);
  btn->selected = FALSE;
  selbar->buttons = g_list_append (selbar->buttons, (gpointer)btn);
}

static void
stub (__attribute__((unused)) WDialog *h) {}


int
mcgdb_aux_dlg(void) {
  WDialog *aux_dlg;
  WTable  *vars_regs_table, *bt_th_table;

  //int wait_gdb=1;
  //while(wait_gdb) {}

  color_selected_frame = tty_try_alloc_color_pair2 ("red", "black", "bold", FALSE);

  vars_regs_table = wtable_new (
    VARS_REGS_WIDGET_Y,
    VARS_REGS_WIDGET_X,
    VARS_REGS_WIDGET_LINES,
    VARS_REGS_WIDGET_COLS
  );
  wtable_add_table(vars_regs_table,"localvars",1);
  wtable_add_table(vars_regs_table,"registers",1);
  wtable_set_current_table(vars_regs_table, "localvars");
  wtable_update_bound(vars_regs_table);

  bt_th_table = wtable_new (
    BT_TH_WIDGET_Y,
    BT_TH_WIDGET_X,
    BT_TH_WIDGET_LINES,
    BT_TH_WIDGET_COLS
  );
  wtable_add_table (bt_th_table,"backtrace",1);
  wtable_add_table (bt_th_table,"threads",1);
  wtable_set_current_table (bt_th_table,"backtrace");
  wtable_update_bound(bt_th_table);

  aux_dlg = dlg_create (FALSE, 0, 0, 0, 0, WPOS_FULLSCREEN, FALSE, NULL, mcgdb_aux_dialog_callback,
                    mcgdb_aux_dialog_mouse_callback, "[GDB]", NULL);
  add_widget (aux_dlg, vars_regs_table);
  add_widget (aux_dlg, bt_th_table);
  VARS_REGS_TABLE_ID    =   WIDGET(vars_regs_table)->id;
  BT_TH_TABLE_ID        =   WIDGET(bt_th_table)->id;
  dlg_run (aux_dlg);
  return 0;
}

void
mcgdb_change_value() {

}


size_t
tty_print_utf8(const char *str) {
  gunichar c;
  gchar *next_ch;
  if (!str || !*str)
    return 0;
  c = g_utf8_get_char_validated (str, -1);
  if (c == (gunichar) (-2) || c == (gunichar) (-1)) {
    tty_print_anychar('.');
    return 1;
  }
  if ((mc_global.utf8_display && g_unichar_isprint (c)) ||
      (!mc_global.utf8_display && is_printable (c)))
  {
      tty_print_anychar(c);
      next_ch = g_utf8_next_char (str);
      return next_ch - str;
  }
  else
  {
      tty_print_anychar('.');
      return 1;
  }
}

size_t
charlength_utf8(const char *str) {
  gunichar c;
  if (!str || !*str)
    return 0;
  c = g_utf8_get_char_validated (str, -1);
  if (c == (gunichar) (-2) || c == (gunichar) (-1))
    return 1;
  return g_utf8_next_char (str) - str;
}