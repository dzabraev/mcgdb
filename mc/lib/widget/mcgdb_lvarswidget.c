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
static void         table_destroy(Table *tab);
static void         table_clear_rows(Table * tab);
static void         table_draw(Table * tab);
static void         table_draw_row (Table * tab, table_row *r);
static void         table_update_colwidth(Table * tab);
static void         table_set_colwidth_formula(Table * tab, int (*formula)(const Table * tab, int ncol));
//static void         table_setcolor(Table *tab, int nrow, int ncol, int color);
static void         table_process_mouse_click(Table *tab, mouse_event_t * event);
static void         table_set_cell_text(Table *tab, int nrow, int ncol, json_t *text);
//static void         table_set_cell_color(Table *tab, int nrow, int ncol, const char *fg, const char *bg, const char *attrib);
static int          formula_eq_col(const Table * tab, int ncol);
//static int          formula_adapt_col(const Table * tab, int ncol);
static void         wtable_update_bound(WTable *wtab);
static void         wtable_draw(WTable *wtab);

static void         table_set_offset(Table *tab, int off);
static void         table_add_offset(Table *tab, int off);
WTable  *           find_wtable (WDialog *h);

static int
print_chunks (GNode *chunk, int x1, int x2, int start_pos, int left_bound, int right_bound, Table *tab, int * rowcnt);

static int
print_str_chunk (cell_data_t *chunk, int x1, int x2, int start_pos, int left_bound, int right_bound, Table * tab, int * rowcnt);

static int
get_chunk_horiz_shift(cell_data_t * chunk);


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


static int
insert_json_row (json_t *row, Table *tab) {
    int nrow;
    json_t * columns = json_object_get (row,"columns");
    size_t rowsize = json_array_size (columns);
    message_assert((size_t)tab->ncols==rowsize);
    nrow = table_add_row (tab);
    for (int ncol=0;ncol<tab->ncols;ncol++) {
      table_set_cell_text (
        tab,nrow,ncol,
        json_array_get (columns,ncol)
      );
    }
    return nrow;
}

static void
insert_pkg_json_into_table (json_t *json_tab, Table *tab) {
  json_t *json_rows = json_object_get (json_tab, "rows");
  size_t size_rows = json_array_size (json_rows);
  json_t *json_selected_row = json_object_get (json_tab,"selected_row");
  int selected_row =  json_selected_row ? json_integer_value (json_selected_row) : -1;
  tab->selected_row = selected_row;
  for (size_t i=0;i<size_rows;i++) {
    json_t * row = json_array_get (json_rows,i);
    insert_json_row (row,tab);
  }
  message_assert (tab->selected_row<tab->nrows);
  //table_add_offset (tab,0);
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
  tab->wtab = wtab;
  table_set_colwidth_formula(tab, formula_eq_col);
  g_hash_table_insert ( wtab->tables, (gpointer) tabname, (gpointer) tab);
  selbar_add_button   ( wtab->selbar, tabname);
}

static void
wtable_set_current_table(WTable *wtab, const char *tabname) {
  wtab->tab = g_hash_table_lookup (wtab->tables, tabname);
  message_assert(wtab->tab!=NULL);
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
  row->columns  = (GNode **)g_new0(GNode *, ncols);
  row->offset   = (int *)g_new(int, ncols);
  row->xl       = (int *)g_new(int, ncols);
  row->xr       = (int *)g_new(int, ncols);
  for (int col=0;col<ncols;col++) {
    row->columns[col] = NULL;
    row->offset[col]=0;
    row->xl[col]=-1;
    row->xr[col]=-1;
  }
  return row;
}

static type_code_t
json_get_chunk_type_code (json_t * chunk) {
  json_t *type_code_json;
  const char *type_code;
  if (!chunk)
    return TYPE_CODE_NONE;
  if ( !(type_code_json= json_object_get (chunk,"type_code")) )
    return TYPE_CODE_NONE;

  type_code = json_string_value (type_code_json);
  if      (!strcmp (type_code,"TYPE_CODE_STRUCT")) {
    return TYPE_CODE_STRUCT;
  }
  else if (!strcmp (type_code,"TYPE_CODE_ARRAY")) {
    return TYPE_CODE_ARRAY;
  }
  else {
    return TYPE_CODE_NONE;
  }
}

static chunk_name_t
json_get_chunk_name (json_t * chunk) {
    const char *name;
    json_t *name_json;
    if (!chunk)
      return CHUNKNAME_NONE;
    name_json = json_object_get (chunk,"name");
    if (!name_json)
      return CHUNKNAME_NONE;
    name = json_string_value (name_json);
    if (!strcmp(name,"frame_num")) {
      return CHUNKNAME_FRAME_NUM;
    }
    else if (!strcmp(name,"th_global_num")) {
      return CHUNKNAME_TH_GLOBAL_NUM;
    }
    else if (!strcmp(name,"varname")) {
      return CHUNKNAME_VARNAME;
    }
    else if (!strcmp(name,"regname")) {
      return CHUNKNAME_REGNAME;
    }
    else if (!strcmp(name,"varvalue")) {
      return CHUNKNAME_VARVALUE;
    }
    else if (!strcmp(name,"regvalue")) {
      return CHUNKNAME_REGVALUE;
    }
    else if (!strcmp(name,"frame_func_name")) {
      return CHUNKNAME_FRAME_FUNC_NAME;
    }
    else if (!strcmp(name,"parenthesis")) {
      return CHUNKNAME_PARENTHESIS;
    }
    else {
      return CHUNKNAME_NONE;
    }
}

static cell_data_t *
cell_data_new (void) {
  cell_data_t * data = g_new0 (cell_data_t, 1);
  data->coord = g_array_new (FALSE,FALSE,sizeof(int));
  data->color = EDITOR_NORMAL_COLOR;
  return data;
}

static void
cell_data_free (cell_data_t * cell_data) {
  g_array_free (cell_data->coord, TRUE);
  if (cell_data->str)
    free (cell_data->str);
  if (cell_data->onclick_data)
    json_decref (cell_data->onclick_data);
  g_free (cell_data);
}

static cell_data_t *
cell_data_new_from_json (json_t * json_chunk) {
  cell_data_t * data = cell_data_new ();
  json_t * onclick_data;
  const char * str;
  json_t *selected;
  if ( (str = json_string_value (json_object_get (json_chunk, "str"))) ) {
    data->str=strdup(str);
  }
  data->type_code = json_get_chunk_type_code (json_chunk);
  if ((selected = json_object_get (json_chunk,"selected"))) {
    if (selected && json_boolean_value(selected))
      data->selected = TRUE;
  }
  if ((onclick_data=json_object_get (json_chunk,"onclick_data"))) {
    json_incref (onclick_data);
    data->onclick_data = onclick_data;
  }
  data->name = json_get_chunk_name (json_chunk);
  data->color = EDITOR_NORMAL_COLOR;
  switch (data->name) {
    case CHUNKNAME_FRAME_NUM:
    case CHUNKNAME_TH_GLOBAL_NUM:
      if (data->selected)
        data->color = tty_try_alloc_color_pair2 ("red", "black", "bold", FALSE);
      break;
    case CHUNKNAME_VARNAME:
    case CHUNKNAME_REGNAME:
      data->color = tty_try_alloc_color_pair2 ("yellow", "blue", NULL, FALSE);
      break;
    case CHUNKNAME_VARVALUE:
    case CHUNKNAME_REGVALUE:
      data->color = tty_try_alloc_color_pair2 ("green", "blue", NULL, FALSE);
      break;
    case CHUNKNAME_FRAME_FUNC_NAME:
      data->color = tty_try_alloc_color_pair2 ("cyan", "blue", NULL, FALSE);
      break;
    default:
      break;
  }
  return data;
}

static void
cell_data_setcolor (cell_data_t *data) {
  tty_setcolor(data->color);
}

static void
json_to_celltree (GNode *parent, json_t *json_chunk) {
  json_t *json_child_chunks = json_object_get (json_chunk, "chunks");
  if (!json_child_chunks)
    return;
  for (size_t nc=0; nc<json_array_size (json_child_chunks); nc++) {
    json_t * json_node_data = json_array_get (json_child_chunks,nc);
    GNode * node = g_node_append_data (parent,cell_data_new_from_json (json_node_data));
    json_to_celltree(node,json_node_data);
  }
}

static void
table_set_cell_text (Table *tab, int nrow, int ncol, json_t *json_data) {
  table_row *row = g_list_nth_data(tab->rows,nrow);
  cell_data_t * cell_data;
  message_assert(row);
  message_assert(row->ncols > ncol);
  if (row->columns[ncol])
    g_node_destroy (row->columns[ncol]);
  cell_data = cell_data_new_from_json (json_data);
  row->columns[ncol] = g_node_new (cell_data);
  json_to_celltree (row->columns[ncol], json_data);
}

static gboolean
is_node_match_yx (GNode *node, int y, int x) {
  cell_data_t * data = CHUNK(node);
  GArray *coord = data->coord;
  if (data->str) {
    message_assert (coord->len%3 == 0);
    for (int i=0;i<coord->len;i+=3) {
      int y1  = g_array_index (coord,int,0);
      int x1 = g_array_index (coord,int,1);
      int x2 = g_array_index (coord,int,2);
      if (y1==y && x>=x1 && x<x2) {
        return TRUE;
      }
    }
    return FALSE;
  }
  else {
    message_assert (coord->len==4);
    int y1 = g_array_index (coord,int,0);
    int x1 = g_array_index (coord,int,1);
    int y2 = g_array_index (coord,int,2);
    int x2 = g_array_index (coord,int,3);
    if (y==y1) {
      if (x>=x1)
        return TRUE;
      else
        return FALSE;
    }
    else if (y==y2) {
      if (x<=x2) {
        return TRUE;
      }
      else {
        return FALSE;
      }
    }
    else if ( y>y1 && y<y2) {
      return TRUE;
    }
    else {
      return FALSE;
    }
  }
}


static GNode *
get_moset_depth_node_with_xy (GNode *node, int y, int x) {
  cell_data_t * data = CHUNK(node);
  if (is_node_match_yx (node,y,x)) {
    if (data->str) {
      return node;
    }
    else {
      GNode *child = g_node_first_child (node);
      while (child) {
        GNode *node1 = get_moset_depth_node_with_xy (child,y,x);
        if (node1)
          return node1;
        child = g_node_next_sibling (child);
      }
      return node;
    }
  }
  else {
    return NULL;
  }
}

static gboolean
process_cell_tree_mouse_callbacks (GNode *root, int y, int x) {
  /*x,y являются абсолютными координатами*/
  gboolean handled = FALSE;
  GNode * node = get_moset_depth_node_with_xy (root,y,x);
  if (node==NULL)
    node=root;
  while (node) {
    json_t * onclick_data = CHUNK(node)->onclick_data;
    if (onclick_data) {
      char *msg;
      asprintf (&msg, "{\"cmd\":\"onclick_data\", \"data\":%s}",json_dumps (onclick_data,0));
      send_pkg_to_gdb (msg);
      free (msg);
      handled=TRUE;
      return handled;
    }
    node=node->parent;
  }
  return handled;
}

static void
table_process_mouse_click(Table *tab, mouse_event_t * event) {
  long click_y = WIDGET(tab->wtab)->y+event->y;
  long click_x  = WIDGET(tab->wtab)->x+event->x;
  GList *g_row = tab->rows;
  long nrow=0,ncol;
  table_row * row;
  gboolean handled=FALSE;
  if (  (click_y <  tab->y) ||
        (click_y >= tab->y+tab->lines) ||
        (click_x <  tab->x) ||
        (click_x >= tab->x+tab->cols)
     ) { /*click out of table*/
     return;
  }
  while(g_row) {
    row = g_row->data;
    if (row->y1<=click_y && row->y2>=click_y) {
      break;
    }
    nrow++;
    g_row=g_row->next;
  }
  if (!g_row)
    return;
  for (ncol=0;ncol<tab->ncols;ncol++) {
    if (tab->colstart[ncol]<=click_x && tab->colstart[ncol+1]>click_x) {
      break;
    }
  }
  /*`nrow` есть номер строки таблицы, по которой был сделан клик.
   *`ncol` есть номер столбца таблицы по которому был сделан клик.
  */
  message_assert (ncol<tab->ncols);

  handled = process_cell_tree_mouse_callbacks(
    TABROW(g_row)->columns[ncol],
    click_y,
    click_x
  );
  if (handled)
    return;

  if (tab->cell_callbacks)
    handled = tab->cell_callbacks[ncol](row,nrow,ncol);
    if (handled)
      return;

  if (tab->row_callback) {
    handled = tab->row_callback(row,nrow,ncol);
    if (handled)
      return;
  }
}

static void
table_row_destroy(table_row *row) {
  for (int col=0;col<row->ncols;col++) {
    g_node_destroy (row->columns[col]);
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


static void
table_set_colwidth_formula(Table * tab, int (*formula)(const Table * tab, int ncol)) {
  tab->formula = formula;
}

static void
tty_setalloc_color (const char *fg, const char *bg, const char * attr, gboolean x) {
  int color = tty_try_alloc_color_pair2 (fg, bg, attr, x);
  tty_setcolor(color);
}

static gboolean
in_printable_area (int colcnt, int left_bound, int right_bound) {
  return colcnt<right_bound && colcnt>=left_bound;
}

static int
print_str_chunk(cell_data_t * chunk_data, int x1, int x2, int start_pos, int left_bound, int right_bound, Table * tab, int * rowcnt) {
  const char * p;
  int offset; //, offset_start;
  int colcnt=start_pos;
  gboolean newline = FALSE;
  /* Массив coord содержит координаты подстрок, на которых напечатан chunk.
   * Массив coord имеет длину 3N, где N--количество строк, занятых chunk'ом.
   * Каждой строке соответствует три последовательно идущих целых числа в массиве coord:
   * y, x_start, x_stop. 
   * `y` есть y-координата строки с учетом смещения.
   * `x_start`, `x_stop` есть координаты начала и конца строки.
   */
  GArray * coord = chunk_data->coord;
  if (coord->len)
    g_array_remove_range (coord, 0, coord->len);
  p = chunk_data->str;
  if (!p)
    p="???";
  offset=ROW_OFFSET(tab,rowcnt[0]);
  //offset_start = offset;
  g_array_append_val (coord, offset);
  g_array_append_val (coord, start_pos);
  tty_gotoyx(offset,start_pos);
  for(;;colcnt++) {
    if(colcnt>=x2 || newline) {
      /*допечатали до правой границы столбца таблицы
       *делаем перенос строки.*/
      int colcnt1 = MIN (colcnt,x2);
      g_array_append_val (coord, colcnt1);
      rowcnt[0]++;
      offset=ROW_OFFSET(tab,rowcnt[0]);
      if (offset>=TAB_TOP(tab) && offset<=TAB_BOTTOM(tab))
        tty_gotoyx(offset,x1);
      colcnt=x1;
      g_array_append_val (coord, offset);
      g_array_append_val (coord, colcnt);
    }
    else if (
      in_printable_area(colcnt,left_bound,right_bound) &&
      !in_printable_area(colcnt-1,left_bound,right_bound)
    ) {
      /* если предыдущая итерация не печатала символ в таблицу,
       * поскольку не позволял row->offset[i], то теперь надо обновить
       * текущую позицию печати.
      */
      offset=ROW_OFFSET(tab,rowcnt[0]);
      tty_gotoyx(offset,left_bound);
    }
    newline=FALSE;
    if (!*p) {
      g_array_append_val (coord, colcnt);
      break;
    }
    switch(*p) {
    case '\n':
      p++;
      if (colcnt!=x1) {
        newline=TRUE;
      }
      break;
    default:
      offset=ROW_OFFSET(tab,rowcnt[0]);
      if (offset>=TAB_TOP(tab) && offset<=TAB_BOTTOM(tab) && in_printable_area(colcnt,left_bound,right_bound)) {
        cell_data_setcolor (chunk_data);
        p+=tty_print_utf8(p);
      }
      else {
        tty_setalloc_color ("brown", "blue", NULL, FALSE);
        if (colcnt>=right_bound) {
          tty_gotoyx(offset,right_bound);
          tty_print_char('>'); /*print on widget frame*/
        }
        else if(colcnt<left_bound) {
          tty_gotoyx(offset,left_bound-1);
          tty_print_char('<'); /*print on widget frame*/
        }
        p+=charlength_utf8(p);
      }
    }
  }
  message_assert (coord->len%3==0);
  return colcnt;
}


static int
print_str(const char * str, int x1, int x2, int start_pos, int left_bound, int right_bound, Table * tab, int * rowcnt) {
  int ret_start_pos;
  cell_data_t * cell_data = cell_data_new ();
  cell_data->str = str;
  ret_start_pos = print_str_chunk(cell_data, x1, x2, start_pos, left_bound, right_bound, tab, rowcnt);
  cell_data->str = NULL;
  cell_data_free (cell_data);
  return ret_start_pos;
}


static int
get_chunk_horiz_shift(cell_data_t * chunk_data) {
  int horiz_shift;
  type_code_t type_code = chunk_data->type_code;
  if (
    type_code == TYPE_CODE_STRUCT ||
    type_code == TYPE_CODE_ARRAY
  ) {
    horiz_shift=2;
  }
  else {
    horiz_shift=0;
  }
  return horiz_shift;
}

static int
print_chunks(GNode * chunk, int x1, int x2, int start_pos, int left_bound, int right_bound, Table *tab, int * rowcnt) {
  message_assert (CHUNK(chunk)!=NULL);
  if (CHUNK(chunk)->str) {
    return print_str_chunk (CHUNK(chunk),x1,x2,start_pos,left_bound,right_bound,tab,rowcnt);
  }
  else {
    type_code_t type_code = CHUNK(chunk)->type_code;
    GArray * coord = CHUNK(chunk)->coord;
    const char *str_begin=0, *str_end=0;
    int horiz_shift = get_chunk_horiz_shift (CHUNK(chunk));
    int start_pos_1;
    int offset;
    GNode *child = g_node_first_child (chunk);

    if (type_code == TYPE_CODE_STRUCT) {
      str_begin="{\n";
      str_end="}\n";
    }
    else if (type_code == TYPE_CODE_ARRAY) {
      str_begin="[\n";
      str_end="]\n";
    }
    if (coord->len>0)
      g_array_remove_range (coord, 0, coord->len);
    offset=ROW_OFFSET(tab,rowcnt[0]);
    g_array_append_val (coord, offset);
    g_array_append_val (coord, start_pos);
    if (str_begin) {
      start_pos = print_str(str_begin,x1,x2,start_pos,left_bound,right_bound,tab,rowcnt);
    }
    /*если chunk есть структура или массив, то начала печатается открывающая скобка с ПЕРЕНОСОМ строки
     *затем печатается тело структуры или массива, после чего печатается закрыающая скобка. Причем
     *тело печатается со сдвигом вправо.
    */
    start_pos_1 = (type_code == TYPE_CODE_STRUCT || type_code == TYPE_CODE_ARRAY) ? (x1+horiz_shift) : (start_pos);
    while (child) {
      start_pos_1 = print_chunks (child,x1+horiz_shift,x2+horiz_shift,start_pos_1,left_bound,right_bound,tab,rowcnt);
      child = g_node_next_sibling (child);
    }
    if (str_end)
      start_pos = print_str(str_end,x1,x2,x1,left_bound,right_bound,tab,rowcnt);
    offset=ROW_OFFSET(tab,rowcnt[0]);
    g_array_append_val (coord, offset);
    g_array_append_val (coord, x1);
    start_pos = (type_code == TYPE_CODE_STRUCT || type_code == TYPE_CODE_ARRAY) ? (x1) : (start_pos_1);
  }

  return start_pos;
}

static void
table_draw_row (Table * tab, table_row *row) {
  /* Переменные x1,x2 являются реальными координатами на экране.
   * row->y1, row->y2 есть реяльные координаты начала и конца строки таблицы.
   * В таблице tab есть параметр row_offset. При помощи данного параметра
   * таблицы сдвигается вверх или вниз.
   * rowcnt есть счетчик, который показывает номер текущей строки (y-координату).
   * offset = rowcnt - row_offset
   * Если часть строки таблицы попадает в допустимый диапазон отрисовки,
   * то данная часть строки будет отрисована.
   *
   * Допустимый диапазон отрисовки таблицы по y-координате зажат между числами
   * TAB_TOP(tab) --ближе к верху экрана  TAB_BOTTOM(tab) -- ближе к низу экрана
   * TAB_TOP(tab) и TAB_BOTTOM(tab) являются реальными координатами на экране.
   */
  long * colstart = tab->colstart;
  GNode ** columns = row->columns;
  GNode  * column;
  int rowcnt;
  long max_rowcnt=1, x1, x2;
  long offset;
  row->y1 = ROW_OFFSET(tab,0);
  for(int i=0;i<tab->ncols;i++) {
    column = columns[i];
    x1 = i==0?colstart[i]:colstart[i]+1;
    x2 = colstart[i+1];
    rowcnt=0;
    offset=ROW_OFFSET(tab,rowcnt);
    if (offset>=TAB_TOP(tab) && offset<=TAB_BOTTOM(tab))
      tty_gotoyx(offset,x1);
    print_chunks (
      column,
      x1 - (row->offset[i]), /*координата самого левого символа ячейки таблицы*/
      x2 - (row->offset[i]), /*до этой координаты будет печататься столбец*/
      x1 - (row->offset[i]), /*позиция, с которой будет печататься первый chunk*/
      x1, /*ограничитель на печать слева*/
      x2, /*ограничитель на печать справа*/
      tab,
      &rowcnt);
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
  table_set_colwidth_formula(tab,formula_eq_col);
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

static void
table_set_offset(Table *tab, int off) {
  tab->row_offset = off;
  table_add_offset (tab,0); /*Если offset вышел за допустимые пределы, то эта
  функция вернет его в пределы.*/
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
        case 'u':
          mcgdb_cmd_frame_up ();
          break;
        case 'd':
          mcgdb_cmd_frame_down ();
          break;
        case 's':
          mcgdb_cmd_step ();
          break;
        case 'n':
          mcgdb_cmd_next ();
          break;
        case 'f':
          mcgdb_cmd_finish ();
        case 'c':
          mcgdb_cmd_continue ();
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
  Table *tab = wtab->tab;
  tty_draw_box (WIDGET(wtab)->y+1, WIDGET(wtab)->x, WIDGET(wtab)->lines-1, WIDGET(wtab)->cols, FALSE);
  if (tab->rows && tab->selected_row>=0) {
    table_draw (tab);
    /* При первичной отрисовке таблицы, помимо прочего, будут посчитаны координаты
     * строк. На основе посчитанных координат вычисляется смещение.
     * Будем изменять смещение если и только если selected_row не видна.
    */
    table_row * selrow;
    int off;
    gboolean changed_off=FALSE;
    message_assert (tab->selected_row < tab->nrows);
    selrow = TABROW(g_list_nth (tab->rows, tab->selected_row));
    if (selrow->y1 <= TAB_TOP(tab) &&  selrow->y2 >= TAB_TOP(tab)) {
      /* верхняя строка ячейки не видна, нижняя видна
       * Делаем, что бы верхняя была видна
       */
      off = selrow->y1 - (TAB_TOP(tab) + 1);
      changed_off = TRUE;
    }
    else if (selrow->y1 <= TAB_BOTTOM(tab) &&  selrow->y2 >= TAB_BOTTOM(tab)) {
      /*нижняя не видна, верхняя видна*/
      off = selrow->y2 - (TAB_BOTTOM(tab) - 1);
      changed_off = TRUE;
    }
    else if (TAB_BOTTOM(tab)<=selrow->y1 || TAB_TOP(tab)>=selrow->y2) {
     /*ничего не видно, перемещаем ячейку в центр*/
     off = (selrow->y2 + selrow->y1)/2 - (TAB_BOTTOM(tab)+TAB_TOP(tab))/2;
     changed_off = TRUE;
    }
    if (changed_off) {
      table_add_offset (tab,off);
      tab->selected_row=-1;
      table_draw (tab);
    }
  }
  else {
    table_add_offset (tab,0); /*make offset valid*/
    table_draw (tab);
  }
  tty_setcolor(EDITOR_NORMAL_COLOR);
  selbar_draw (wtab->selbar);
  wtab->tab->redraw = REDRAW_NONE;
}

static void
chunks_find_xlr (GNode * chunk, int *xl, int *xr) {
  if (CHUNK(chunk)->str) {
    GArray * coord = CHUNK(chunk)->coord;
    message_assert (CHUNK(chunk)->coord->len>0);
    for (size_t i=0; i<coord->len;i+=3) {
      int x_start = g_array_index (coord,int,i+1);
      int x_stop  = g_array_index (coord,int,i+2);
      if (x_stop - x_start >= 1) {
        *xl = MIN(*xl, x_start);
        *xr = MAX(*xr, x_stop);
        message_assert (*xr >= *xl);
      }
    }
  }
  else {
    GNode * child = g_node_first_child (chunk);
    while (child) {
      chunks_find_xlr (child, xl, xr);
      child = g_node_next_sibling (child);
    }
  }
}

static void
update_cell_width(table_row * tr, int ncol) {
  /*вычислим самую левую координату по всем chunk'ам ячейки и
  самую правую координату*/
  int xl=0xfffff, xr=-0xfffff;
  chunks_find_xlr(tr->columns[ncol], &xl, &xr);
  message_assert (xl!=0xfffff);
  message_assert (xr!=-0xfffff);
  tr->xl[ncol] = xl;
  tr->xr[ncol] = xr;
}

static void
table_process_mouse_down(Table *tab, mouse_event_t * event) {
  GList * row = tab->rows;
  table_row *tr;
  tab->mouse_down_x = event->x;
  tab->mouse_down_y = event->y;
  int ncol;
  while(row) {
    tr = (table_row *)(row->data);
    if (tr->y1<=event->y && event->y<tr->y2)
      break;
    row=row->next;
  }
  if (!row)
    return;
  for (ncol=0;ncol<tr->ncols;ncol++) {
    int x0 = WIDGET(tab->wtab)->x; /* х-координата начала виджета*/
    if (((tab->colstart[ncol] - x0) <= event->x) && /*транслируем абсолютные коорд. окна в коорд. виджета*/
          (event->x < (tab->colstart[ncol+1]-x0)))
      break;
  }
  if (ncol==tr->ncols)
    return;
  tab->active_row = tr;
  tab->active_col = ncol;
  update_cell_width(tr,ncol);
}

static void
table_process_mouse_up(Table *tab, mouse_event_t * event) {
  tab->active_row = NULL;
}

static void
table_process_mouse_drag(Table *tab, mouse_event_t * event) {
  int L,ncol;
  table_row *tr = tab->active_row;
  if (!tr)
    return;
  ncol = tab->active_col;
  tr->offset[ncol] += tab->mouse_down_x - event->x;
  tr->offset[ncol] = MAX (tr->offset[ncol],0);
  L = MAX((tr->xr[ncol] - tr->xl[ncol]) - (tab->colstart[ncol+1]-tab->colstart[ncol]),0);
  tr->offset[ncol] = MIN (tr->offset[ncol],L);
  tab->mouse_down_x = event->x;
  tab->redraw |= REDRAW_TAB;
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
      table_process_mouse_click(wtab->tab, event);
      break;
    case MSG_MOUSE_DOWN:
      table_process_mouse_down(wtab->tab, event);
      break;
    case MSG_MOUSE_DRAG:
      table_process_mouse_drag(wtab->tab, event);
      break;
    case MSG_MOUSE_UP:
      table_process_mouse_up(wtab->tab, event);
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