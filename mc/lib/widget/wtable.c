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
#include "lib/widget/wtable.h"

#include "lib/tty/tty.h"
#include "lib/skin.h"

#include "lib/util.h"

#include <jansson.h>

#define ROW_OFFSET(tab,rowcnt) (((tab)->last_row_pos)+(rowcnt))
#define TAB_BOTTOM(tab) ((tab)->y+(tab)->lines - 1)
#define TAB_TOP(tab) ((tab)->y)


static cb_ret_t wtable_callback           (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);
static cb_ret_t selbar_callback           (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);

static void wtable_mouse_callback           (Widget * w, mouse_msg_t msg, mouse_event_t * event);
static void selbar_mouse_callback           (Widget * w, mouse_msg_t msg, mouse_event_t * event);

size_t tty_print_utf8(const char *str, gboolean blank);
size_t charlength_utf8(const char *str);

static table_row *  table_row_alloc(long ncols);
static void         table_row_destroy(table_row *row);
static void         table_update_bounds(Table * tab, long y, long x, long lines, long cols);
static Table *      table_new (const char *table_name, long ncols);
static Table *      table_copy (const Table *tab);
static int          table_add_row (Table * tab);
static void         table_destroy(Table *tab);
static void         table_clear_rows(Table * tab);
static void         table_draw(Table * tab);
static void         table_compute_lengths(Table * tab);
static void         __table_draw(Table * tab, gboolean blank);

static void         table_draw_row (Table * tab, table_row *r, gboolean blank);
static void         table_update_colwidth(Table * tab);
static void         table_set_colwidth_formula(Table * tab, int (*formula)(const Table * tab, int ncol));
//static void         table_setcolor(Table *tab, int nrow, int ncol, int color);
static void         table_process_mouse_click(Table *tab, mouse_event_t * event);
static void         table_set_cell_text(Table *tab, int nrow, int ncol, json_t *text);
//static void         table_set_cell_color(Table *tab, int nrow, int ncol, const char *fg, const char *bg, const char *attrib);
static void         table_update_node_json (Table *tab, json_t *json_chunk);

static int          formula_eq_col(const Table * tab, int ncol);
//static int          formula_adapt_col(const Table * tab, int ncol);
static void         table_do_row_visible(Table *tab, int nrow);
static void         table_set_offset(Table *tab, int off);
static void         table_add_offset(Table *tab, int off);
WTable  *           find_wtable (WDialog *h);

static int
print_chunks (GNode *chunk, int x1, int x2, int start_pos, int left_bound, int right_bound, Table *tab, int * rowcnt, gboolean blank);

static int
print_str_chunk (cell_data_t *chunk, int x1, int x2, int start_pos, int left_bound, int right_bound, Table * tab, int * rowcnt, gboolean blank);

static int
get_chunk_horiz_shift(cell_data_t * chunk);


gint    find_button_in_list(gconstpointer a, gconstpointer b);

Selbar *find_selbar (WDialog *h);


static  Selbar *selbar_new (int y, int x, int height, int width);
void    selbar_add_button(Selbar *selbar, const char * text);
void    ghfunc_table_update_bounds(__attribute__((unused)) gpointer key, gpointer value, gpointer user_data);
static void     selbar_set_current_button(Selbar *selbar, const char *tabname);
static void     selbar_draw (Selbar *bar);
static void     reset_selected (gpointer data, gpointer user_data);

/*Функция `wtable_do_row_visible_json` осуществляет перемотку содержимого таблицы tabname так,
что бы строка с номером nrow стала видимой*/
static void
wtable_do_row_visible_json(WTable *wtab, json_t *pkg);

static void
wtable_exemplar_create(WTable *wtab, json_t *pkg);

static void
wtable_exemplar_drop(WTable *wtab, json_t *pkg);

static void
wtable_exemplar_set(WTable *wtab, json_t *pkg);

static void
wtable_exemplar_copy(WTable *wtab, json_t *pkg);

static void
wtable_insert_exemplar (WTable *wtab, Table *tab, const char *table_name, gint id);

static void
wtable_update_node(WTable *wtab, json_t *pkg);

static void
wtable_do_row_visible(WTable *wtab, const char *tabname, gint id, int nrow);

static Table *
wtable_get_exemplar (WTable *wtab, const char *table_name, gint id);

static GHashTable *
wtable_get_exemplars (WTable *wtab, const char *table_name);


static void
insert_pkg_json_into_table (json_t *json_tab, Table *tab);


static cell_data_t * cell_data_new (void);
static cell_data_t * cell_data_copy (const cell_data_t * data);

static Table *
get_exemplar(GHashTable *exemplars, gint id);












static table_row *
TAB_LAST_ROW(Table * tab) {
  return (tab->rows) ? (table_row *)(g_list_last (tab->rows)->data) : NULL;
}

static table_row *
TAB_FIRST_ROW(Table * tab) {
  return tab->rows ? (table_row *)(tab->rows->data) : NULL;
}

static global_keymap_t *
wtable_get_tab_keymap(WTable *wtab, const char *tabname) {
  return g_hash_table_lookup (wtab->keymap, tabname);
}

static void
wtable_exemplar_copy(WTable *wtab, json_t *pkg) {
/*
  pkg = {
    'cmd' : 'exemplar_copy'
    'id' : int,
    'new_id': int,
    'table_name' : str,
  }
*/
  const char *table_name = json_str(pkg,"table_name");
  gint new_id = json_int(pkg,"new_id");
  Table *tab = table_copy (wtable_get_table (wtab,table_name));
  wtable_insert_exemplar (wtab,tab,table_name,new_id);
}

static Table *
wtable_get_exemplar (WTable *wtab, const char *table_name, gint id) {
  /*Если id!=0, то возвращается экземляр по id, иначе возвр. текущий экземпляр.*/
  if (id)
    return get_exemplar(wtable_get_exemplars (wtab,table_name),id);
  else
    return wtable_get_table (wtab,table_name);
}

static GHashTable *
wtable_get_exemplars (WTable *wtab, const char *table_name) {
  return (GHashTable *) g_hash_table_lookup (wtab->tables_exemplars, (gpointer) table_name);
}

static Table *
get_exemplar(GHashTable *exemplars, gint id) {
  message_assert (exemplars!=NULL);
  return (Table *) g_hash_table_lookup (exemplars, GINT_TO_POINTER(id));
}

static void
__wtable_exemplar_drop(WTable *wtab, const char *table_name, gint id) {
  GHashTable * exemplars=wtable_get_exemplars (wtab, table_name);
  Table *tab = get_exemplar (exemplars, id);
  Table *curtable = g_hash_table_lookup (wtab->tables, table_name);
  message_assert (tab!=NULL); /*we try delete not existing table. probably it is error.*/
  if (curtable==tab) {
    /*удаление таблицы, которая является текущей для наименования table_name*/
    g_hash_table_replace (
      wtab->tables,
      strdup (table_name),
      get_exemplar (exemplars,TABID_EMPTY_TABLE));
  }

  if (tab==wtab->tab) {
    /*запрос на удаление экземпляра, который отрисовывается сейчас.*/
    /*ставим на орисовку пустой экземпляр*/
    wtab->tab = get_exemplar (exemplars,TABID_EMPTY_TABLE);
  }
  g_hash_table_remove (exemplars, GINT_TO_POINTER(id));
  table_destroy (tab);
}

static void
wtable_exemplar_drop(WTable *wtab, json_t *pkg) {
/* pkg = {
*    'cmd' : 'exemplar_drop'
*    'id' : int,
*    'table_name' : str,
*  }
*/
  const char *table_name = json_str (pkg, "table_name");
  gint id = json_int(pkg,"id");
  __wtable_exemplar_drop(wtab,table_name,id);
}


static void
wtable_insert_exemplar (WTable *wtab, Table *tab, const char *table_name, gint id) {
  /*insert exemplar `tab` to `table_name` exemplars. If exemplar with given id exists, remove old exemplar.*/
  GHashTable * exemplars = wtable_get_exemplars (wtab, table_name);
  Table *old_tab;
  message_assert (exemplars!=NULL);
  old_tab = g_hash_table_lookup (exemplars,GINT_TO_POINTER(id));
  if (old_tab) {
    if (old_tab) {
      /*с таким id существовал экземпляр. Наследуем от него row_offset*/
      tab->row_offset = old_tab->row_offset;
    }
    __wtable_exemplar_drop (wtab,table_name,id);
  }
  g_hash_table_insert (exemplars, GINT_TO_POINTER(id), (gpointer) tab);
}


static void
wtable_set_current_exemplar(WTable *wtab, const char *table_name, gint id) {
  /* устанавливает таблицу текущей для наименования table_name. При этом, если текущее наименование
   * отрисовки совпадает с table_name, то будет изменена таблица, которая будет отрисовываться.*/
  GHashTable *exemplars = wtable_get_exemplars (wtab,table_name);
  Table *tab, *old_tab;
  message_assert (exemplars!=NULL);
  tab = get_exemplar (exemplars,id);
  message_assert (tab!=NULL);
  old_tab = g_hash_table_lookup (wtab->tables, table_name);
  if (old_tab->id==id) {
    /*this table already set for draw*/
    return;
  }
  message_assert (old_tab!=NULL);
  if (TABLE_IS_TMP(old_tab)) {
    /*Если таблица, которая была текущей для наименование table_name
     * была временной, то в этом случае ее нужно удалить. При этом если устанавливается
     * так же самая таблица, то таблица не удаляется*/
    __wtable_exemplar_drop (wtab,table_name,old_tab->id);
  }
  g_hash_table_replace (wtab->tables, strdup(table_name), (gpointer) tab); /*set current table*/
  if (!strcmp(wtab->current_table_name,tab->table_name)) {
    /*Если в данный момент отрисовывается наименование table_name, тогда ставим
     *данную таблицу на отрисовку*/
    wtab->tab=tab;
    wtab->tab->redraw = REDRAW_TAB;
  }
}

static void
wtable_exemplar_set(WTable *wtab, json_t *pkg) {
/* pkg = {
*    'cmd' : 'exemplar_set'
*    'id' : int,
*    'table_name' : str,
*  }
*/
  const char *table_name = json_str (pkg, "table_name");
  gint id = json_int(pkg,"id");
  wtable_set_current_exemplar (wtab,table_name,id);
}

static Table *
__wtable_exemplar_create (WTable *wtab, const char *table_name, gint id, json_t *table) {
  int ncols;
  Table *tab;
  if (!table) {
    ncols=0;
  }
  else {
   json_t *rows = json_arr (table, "rows");
    if (json_array_size(rows)==0) /*no rows*/
      ncols=0;
    else {
      ncols = json_array_size(json_arr (json_array_get(rows,0),"columns")); /*length of first row*/
    }
  }
  tab = table_new(table_name, ncols);
  tab->wtab = wtab;
  tab->id = id;
  tab->keymap = wtable_get_tab_keymap(wtab,table_name);
  if (table) {
    insert_pkg_json_into_table (table,tab); /*заполнение таблицы данными из пакета*/
  }
  wtable_insert_exemplar (wtab, tab, table_name, id);
  return tab;
}

static void
wtable_exemplar_create (WTable *wtab, json_t *pkg) {
/*
  pkg = {
    'cmd' : 'exemplar_create'
    'id' : int,
    'table_name' : str,
    'table' : str,
    'set' : Bool, #if True, this exemplar will be set as current for table_name
  }
*/
  const char *table_name = json_str (pkg, "table_name");
  gint id = json_int (pkg, "id");
  json_t *table = json_obj (pkg, "table");

   __wtable_exemplar_create (wtab, table_name, id, table);

  if (json_boolean_value(json_object_get(pkg,"set"))) {
    wtable_set_current_exemplar (wtab,table_name,id);
  }
}


gboolean
wtable_gdbevt_common (WTable *wtab, gdb_action_t * act) {
  /*return TRUE if event was processed*/
  json_t *pkg = act->pkg;
  gboolean handled=FALSE;
  switch(act->command) {
    case MCGDB_EXEMPLAR_CREATE:
      wtable_exemplar_create (wtab,pkg);
      handled=TRUE;
      break;
    case MCGDB_EXEMPLAR_DROP:
      wtable_exemplar_drop (wtab,pkg);
      handled=TRUE;
      break;
    case MCGDB_EXEMPLAR_SET:
      wtable_exemplar_set (wtab,pkg);
      handled=TRUE;
      break;
    case MCGDB_EXEMPLAR_COPY:
      wtable_exemplar_copy (wtab,pkg);
      handled=TRUE;
      break;
    case MCGDB_UPDATE_NODE:
      wtable_update_node(wtab,pkg);
      handled=TRUE;
      break;
    case MCGDB_DO_ROW_VISIBLE:
      wtable_do_row_visible_json(wtab,pkg);
      handled=TRUE;
      break;
    default:
      break;
  }
  if (NEED_REDRAW(wtab))
    wtable_draw(wtab);
  return handled;
}


static int
insert_json_row (json_t *row, Table *tab) {
    int nrow;
    json_t * columns = json_arr (row,"columns");
    size_t rowsize = json_array_size (columns);
    message_assert((size_t)(tab->ncols)==rowsize);
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
  json_t *json_rows = json_arr (json_tab, "rows");
  size_t size_rows = json_array_size (json_rows);
  json_t *json_selected_row = json_object_get (json_tab,"selected_row");
  json_t *draw;
  tab->selected_row = json_selected_row ? json_integer_value (json_selected_row) : -1;
  if ((draw = json_object_get (json_tab,"draw_vline"))) {
    tab->draw_vline = json_boolean_value (draw);
  }
  if ((draw = json_object_get (json_tab,"draw_hline"))) {
    tab->draw_hline = json_boolean_value (draw);
  }
  for (size_t i=0;i<size_rows;i++) {
    json_t * row = json_array_get (json_rows,i);
    insert_json_row (row,tab);
  }
}


void
ghfunc_table_update_bounds(__attribute__((unused)) gpointer key, gpointer value, gpointer user_data) {
  //WTable * wtab = WTABLE(user_data);
  //Widget * w = WIDGET(wtab);
  Table  * tab  = TABLE(value);
  tab->lengths_outdated=TRUE;
  //table_update_bounds(tab, w->y+2,w->x+1,w->lines-3,w->cols-2);
  //table_compute_lengths (tab);
}

void
wtable_update_bound(WTable *wtab) {
  Selbar *selbar = wtab->selbar;
  g_hash_table_foreach (wtab->tables, ghfunc_table_update_bounds, wtab);
  selbar->x     = WIDGET(wtab)->x;
  selbar->y     = WIDGET(wtab)->y;
  selbar->cols  = WIDGET(wtab)->cols;
  selbar->lines = 1;
}

void
wtable_update_node(WTable *wtab, json_t *pkg) {
  json_t *json_chunk = json_obj (pkg,"node_data");
  const char *tabname = json_str (pkg,"table_name");
  Table *tab = wtable_get_table(wtab,tabname);
  message_assert (json_chunk!=NULL);
  table_update_node_json(tab,json_chunk);
}

WTable *
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
    wtab->keymap = g_hash_table_new (g_str_hash,  g_str_equal);
    wtab->tables = g_hash_table_new_full (g_str_hash,  g_str_equal, free, NULL);
    wtab->tables_exemplars = g_hash_table_new_full (g_str_hash,  g_str_equal, NULL, (GDestroyNotify) g_hash_table_destroy);
    wtab->selbar = selbar_new (y,x,1,width);
    return wtab;
}

void
wtable_add_table(WTable *wtab, const char *table_name, const global_keymap_t * keymap) {
  Table *tab;
  g_hash_table_insert (wtab->keymap, (gpointer) strdup(table_name), (gpointer) keymap);
  g_hash_table_insert (
    wtab->tables_exemplars,
    (gpointer) strdup(table_name),
    (gpointer) g_hash_table_new (g_direct_hash, g_direct_equal));
  selbar_add_button (wtab->selbar, table_name);
  tab = __wtable_exemplar_create (wtab, table_name, TABID_EMPTY_TABLE, NULL);
  g_hash_table_insert (wtab->tables, (gpointer) strdup(table_name), (gpointer) tab);

}

void
wtable_set_tab(WTable *wtab, const char *tabname) {
  /*установить вкладку с текстом tabname текущей*/
  message_assert (wtab!=NULL);
  wtab->tab = g_hash_table_lookup (wtab->tables, tabname);
  message_assert (wtab->tab != NULL);
  wtab->current_table_name = wtab->tab->table_name;
  selbar_set_current_button(wtab->selbar,tabname);
  wtab->tab->redraw = TRUE;
}

Table *
wtable_get_table(WTable *wtab, const char *table_name) {
  message_assert (table_name!=NULL);
  return g_hash_table_lookup (wtab->tables, table_name);
}

static gpointer
table_cell_data_copy(gconstpointer src, gpointer data) {
  Table *tab = (Table *)data;
  cell_data_t * new_node = cell_data_copy((cell_data_t *)src);
  if (new_node->id) {
    g_hash_table_insert ( tab->hnodes, GINT_TO_POINTER(new_node->id), new_node);
  }
  return new_node;
}

static table_row *
table_row_copy(Table *tab, const table_row *row) {
  /*Копирует строку row в таблицу tab. Предполагается, что row
   *принадлежит отличной от tab таблице. При копировании деревьев(chunks)
   *для каждой ячейки столбца будет осуществляться добавление пар (node_id,pointer)
   *в хэш-таблицу tab->hnodes
   */
  long ncols = row->ncols;
  table_row * new_row = g_new0 (table_row,1);
  new_row->ncols=row->ncols;
  new_row->y1 = row->y1;
  new_row->y2 = row->y2;
  new_row->columns  = (GNode **)g_new0(GNode *, ncols);
  new_row->offset   = (int *)g_new(int, ncols);
  new_row->xl       = (int *)g_new(int, ncols);
  new_row->xr       = (int *)g_new(int, ncols);
  for (int col=0;col<ncols;col++) {
    new_row->columns[col] = g_node_copy_deep (row->columns[col],table_cell_data_copy,(gpointer) tab);
    new_row->offset[col]  = row->offset[col];
    new_row->xl[col]      = row->xl[col];
    new_row->xr[col]      = row->xr[col];
  }
  tab->rows = g_list_append (tab->rows, new_row);
  return new_row;
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
  else if (!strcmp (type_code,"TYPE_CODE_UNION")) {
    return TYPE_CODE_UNION;
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
    else if (!strcmp(name,"asm_op")) {
      return CHUNKNAME_ASM_OP;
    }
    else {
      return CHUNKNAME_NONE;
    }
}

static Table *
table_copy (const Table *tab) {
  /*copy constructor*/
  gint idx;
  Table *new_tab = g_new0(Table,1);
  memcpy(new_tab,tab,sizeof(Table));

  new_tab->active_row=NULL;
  new_tab->rows=NULL;

  new_tab->colstart=g_new(long,(new_tab->ncols+1));
  memcpy(new_tab->colstart,tab->colstart,(tab->ncols+1)*sizeof(long));

  /*copy rows of `tab` into `new_tab`. При копировании
   *будет осуществлено заполнение new_tab->hnodes
   */
  new_tab->hnodes = g_hash_table_new (g_direct_hash, g_direct_equal);
  for(GList *row=tab->rows;row;row=row->next) {
    table_row_copy (new_tab,(const table_row *)(row->data));
  }
  message_assert (g_hash_table_size(tab->hnodes)==g_hash_table_size(new_tab->hnodes));
  if (tab->active_row) {
    idx=g_list_index(tab->rows, (gconstpointer)(tab->active_row));
    new_tab->active_row = (table_row *) g_list_nth_data(new_tab->rows,idx);
  }
  return new_tab;
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

static void
cell_data_makecolor(cell_data_t *data) {
  if (data->selected) {
    data->color = tty_try_alloc_color_pair2 ("red", "black", "bold", FALSE);
    return;
  }
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
    case CHUNKNAME_ASM_OP:
      data->color = tty_try_alloc_color_pair2 ("yellow", "blue", NULL, FALSE);
      break;
    default:
      data->color = EDITOR_NORMAL_COLOR;
      break;
  }
}

/*
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
  gint id;
} cell_data_t;
*/

static cell_data_t *
cell_data_copy (const cell_data_t * data) {
  cell_data_t * new_data = cell_data_new();
  new_data->name = data->name;
  new_data->type_code = data->type_code;
  new_data->str = strdup(data->str);
  new_data->proposed_text = strdup(data->proposed_text);
  memcpy(new_data->coord,data->coord,data->coord->len*sizeof(int));
  new_data->color = data->color;
  new_data->selected = data->selected;
  new_data->onclick_data = json_deep_copy(data->onclick_data);
  new_data->onclick_user_input = data->onclick_user_input;
  new_data->id = data->id;
  return new_data;
}

static cell_data_t *
cell_data_new_from_json (json_t * json_chunk) {
  cell_data_t * data = cell_data_new ();
  json_t * onclick_data, * json_id;
  const char *str, *proposed_text;
  json_t *selected;
  if ( (str = json_string_value (json_object_get (json_chunk, "str"))) ) {
    data->str=strdup(str);
  }
  if ( (json_id = json_object_get(json_chunk,"id")) ) {
    data->id = json_integer_value (json_id);
    message_assert (data->id!=0);
  }
  else {
    data->id = 0;
  }
  if ( (proposed_text = json_string_value (json_object_get (json_chunk, "proposed_text"))) ) {
    data->proposed_text=strdup(proposed_text);
  }
  data->type_code = json_get_chunk_type_code (json_chunk);
  if ((selected = json_object_get (json_chunk,"selected"))) {
    if (selected && json_boolean_value(selected))
      data->selected = TRUE;
      data->color = tty_try_alloc_color_pair2 ("red", "black", "bold", FALSE);
  }
  if ((onclick_data=json_object_get (json_chunk,"onclick_data"))) {
    json_incref (onclick_data);
    data->onclick_data = onclick_data;
  }
  if (json_object_get (json_chunk,"onclick_user_input"))
    data->onclick_user_input=TRUE;
  else
    data->onclick_user_input=FALSE;
  data->name = json_get_chunk_name (json_chunk);
  cell_data_makecolor(data);
  return data;
}

static void
cell_data_setcolor (cell_data_t *data) {
  tty_setcolor(data->color);
}


static GNode *
table_get_node_by_id (Table * tab, gint node_id) {
  return (GNode *) g_hash_table_lookup (tab->hnodes, GINT_TO_POINTER(node_id));
}


static void
update_chunk (cell_data_t * data, json_t * json_data) {
#define update_prop(data,newdata,json_data,key) do {\
  if (json_object_get(json_data,#key)) {\
    data->key=newdata->key;\
  }\
} while(0)
  cell_data_t * cell_data = cell_data_new_from_json (json_data);
  if (json_object_get(json_data,"str")) {
    free(data->str);
    data->str = cell_data->str;
  }
  if (json_object_get(json_data,"proposed_text")) {
    free(data->proposed_text);
    data->proposed_text = cell_data->proposed_text;
  }
  if (json_object_get(json_data,"onclick_data")) {
    json_decref (data->onclick_data);
    data->onclick_data = cell_data->onclick_data;
  }
  //update_prop(data,cell_data,json_data,str);
  //update_prop(data,cell_data,json_data,proposed_text,free);
  update_prop(data,cell_data,json_data,selected);
  //update_prop(data,cell_data,json_data,onclick_data);
  update_prop(data,cell_data,json_data,onclick_user_input);
  update_prop(data,cell_data,json_data,name);
  cell_data_makecolor(data);
  free(cell_data);
}


static GNode *
table_add_node(Table *tab, GNode * parent, json_t *json_data) {
  cell_data_t *data = cell_data_new_from_json (json_data);
  GNode *node = g_node_append_data (parent,data);
  if (data->id)
    g_hash_table_insert ( tab->hnodes, GINT_TO_POINTER(data->id), node);
  return node;
}


static gboolean
drop_childs_free (GNode *node, gpointer data) {
  cell_data_free ((cell_data_t *)node->data);
  node->data=NULL;
  return FALSE;
}

static void
drop_childs (GNode *node) {
  GNode *child = g_node_first_child (node);
  while (child) {
    g_node_unlink (child);
    g_node_traverse (child,G_IN_ORDER,G_TRAVERSE_ALL,-1,drop_childs_free,0);
    g_node_destroy (child);
    child = g_node_first_child (node);
  }
}

static void
json_to_celltree (Table *tab, GNode *parent, json_t *json_chunk) {
  json_t *json_child_chunks = json_object_get (json_chunk, "chunks");
  if (!json_child_chunks)
    return;
  for (size_t nc=0; nc<json_array_size (json_child_chunks); nc++) {
    json_t * json_node_data = json_array_get (json_child_chunks,nc);
    GNode * node = table_add_node (tab,parent,json_node_data);
    json_to_celltree(tab,node,json_node_data);
  }
}


static void
table_update_node_json (Table *tab, json_t *json_chunk) {
  gint node_id;
  GNode *node;
  node_id = json_int (json_chunk, "id");
  node = table_get_node_by_id (tab, node_id);
  message_assert (node!=NULL);
  update_chunk(CHUNK(node),json_chunk);
  if (json_object_get (json_chunk, "chunks")) {
    /*if new data has subtree => replace old subtree*/
    drop_childs(node);
    json_to_celltree(tab,node,json_chunk);
  }
  tab->lengths_outdated=TRUE;
}



static void
table_set_cell_text (Table *tab, int nrow, int ncol, json_t *json_data) {
  table_row *row = g_list_nth_data(tab->rows,nrow);
  cell_data_t * cell_data;
  GNode *cell_root;
  message_assert(row);
  message_assert(row->ncols > ncol);
  if (row->columns[ncol])
    g_node_destroy (row->columns[ncol]);
  cell_data = cell_data_new_from_json (json_data);
  cell_root = g_node_new (cell_data);
  row->columns[ncol] = cell_root;
  if (json_object_get (json_data, "id"))
    g_hash_table_insert (tab->hnodes, GINT_TO_POINTER(cell_data->id), cell_root);
  json_to_celltree (tab, row->columns[ncol], json_data);
}

static gboolean
is_node_match_yx (GNode *node, int y, int x) {
  cell_data_t * data = CHUNK(node);
  GArray *coord = data->coord;
  if (data->str) {
    message_assert (coord->len%3 == 0);
    for (unsigned int i=0;i<coord->len;i+=3) {
      int y1 = g_array_index (coord,int,i+0);
      int x1 = g_array_index (coord,int,i+1);
      int x2 = g_array_index (coord,int,i+2);
      if (y1==y && x>=x1 && x<x2) {
        return TRUE;
      }
    }
    return FALSE;
  }
  else {
    int x1,x2,y1,y2;
    message_assert (coord->len==4);
    y1 = g_array_index (coord,int,0);
    x1 = g_array_index (coord,int,1);
    y2 = g_array_index (coord,int,2);
    x2 = g_array_index (coord,int,3);
    if (y1==y2 && y==y1) {
      return (x>=x1) && (x<x2);
    }
    else {
      if (y==y1) {
        if (x>=x1)
          return TRUE;
        else
          return FALSE;
      }
      else if (y==y2) {
        if (x<x2) {
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
}


static GNode *
get_moset_depth_node_with_yx (GNode *node, int y, int x) {
  cell_data_t * data = CHUNK(node);
  if (is_node_match_yx (node,y,x)) {
    if (data->str) {
      return node;
    }
    else {
      GNode *child = g_node_first_child (node);
      while (child) {
        GNode *node1 = get_moset_depth_node_with_yx (child,y,x);
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
process_cell_tree_mouse_callbacks (Table *tab, GNode *root, int y, int x) {
  /*x,y являются абсолютными координатами*/
  gboolean handled = FALSE;
  gboolean insert_wait_text=FALSE;
  GNode * node;
  message_assert (tab!=NULL);
  message_assert (root!=NULL);
  node = get_moset_depth_node_with_yx (root,y,x);
  if (node==NULL)
    node=root;
  while (node) {
    json_t * onclick_data = CHUNK(node)->onclick_data;
    if (onclick_data) {
      char *f=NULL;
      json_t * msg_obj;
      if (CHUNK(node)->onclick_user_input) {
        f = input_dialog (
          _("Change variable"),
          json_string_value (json_object_get (onclick_data, "input_text")),
          "mc.edit.change-variable",
           CHUNK(node)->proposed_text ? CHUNK(node)->proposed_text  : CHUNK(node)->str,
          INPUT_COMPLETE_NONE);
        if (f == NULL || *f == '\0') {
          /*user cancel*/
          g_free (f);
          handled=TRUE;
          return handled;
        }
        insert_wait_text=TRUE;
      }
      msg_obj = json_deep_copy (onclick_data);
      json_object_set_new (msg_obj, "user_input", json_string (f));
      send_pkg_to_gdb (json_dumps (msg_obj,0));
      json_decref (msg_obj);

/*
      msg_obj = json_object();
      json_object_set_new (msg_obj, "cmd", json_string ("onclick"));
      json_object_set (msg_obj, "data", onclick_data);
      json_object_set_new (msg_obj, "user_input", json_string (f));
      send_pkg_to_gdb (json_dumps (msg_obj,0));
      json_decref (msg_obj);
*/
      if (insert_wait_text) {
        //message_assert (CHUNK(node)->str);
        if (CHUNK(node)->str)
          free (CHUNK(node)->str);
        drop_childs(node);
        asprintf(&CHUNK(node)->str,"<Wait change: %s>", f);
        json_decref (CHUNK(node)->onclick_data);
        CHUNK(node)->onclick_data=NULL;
        CHUNK(node)->color=EDITOR_NORMAL_COLOR;
        tab->redraw|=REDRAW_TAB;
        tab->lengths_outdated=TRUE; /*была изменена текстовая строка=>надо пересчитать длины*/
      }
      g_free (f);
      handled=TRUE;
      return handled;
    }
    node=node->parent;
  }
  return handled;
}

static void
table_process_mouse_click(Table *tab, mouse_event_t * event) {
  long click_y, click_x;
  GList *g_row;
  long nrow=0,ncol;
  table_row * row;
  gboolean handled=FALSE;

  message_assert (tab!=NULL);

  click_y = WIDGET(tab->wtab)->y+event->y;
  click_x  = WIDGET(tab->wtab)->x+event->x;
  g_row = tab->rows;

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
    tab,
    TABROW(g_row)->columns[ncol],
    click_y,
    click_x
  );

/*
  if (!handled && tab->cell_callbacks)
    handled = tab->cell_callbacks[ncol](row,nrow,ncol);

  if (!handled && tab->row_callback) {
    handled = tab->row_callback(row,nrow,ncol);
  }
*/
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
  if (!tab)
    return
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

void
wtable_set_colwidth_formula(WTable *wtab, const char *tabname, int (*formula)(const Table * tab, int ncol)) {
  Table *tab = wtable_get_table (wtab,tabname);
  table_set_colwidth_formula (tab, formula);
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
print_str_chunk(cell_data_t * chunk_data, int x1, int x2, int start_pos, int left_bound, int right_bound, Table * tab, int * rowcnt, gboolean blank) {
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
  GArray * coord;
  message_assert (tab!=NULL);
  coord = chunk_data->coord;
  if (blank && coord->len)
    g_array_remove_range (coord, 0, coord->len);
  p = chunk_data->str;
  if (!p)
    p="???";
  offset=ROW_OFFSET(tab,rowcnt[0]);
  //offset_start = offset;
  if (blank) {
    g_array_append_val (coord, offset);
    g_array_append_val (coord, start_pos);
  }
  if (!blank)
    tty_gotoyx(offset,start_pos);
  for(;;) {
    if(colcnt>=x2 || newline) {
      /*допечатали до правой границы столбца таблицы
       *делаем перенос строки.*/
      int colcnt1 = MIN (colcnt,x2);
      if (blank)
        g_array_append_val (coord, colcnt1);
      rowcnt[0]++;
      offset=ROW_OFFSET(tab,rowcnt[0]);
      if (!blank && offset>=TAB_TOP(tab) && offset<=TAB_BOTTOM(tab))
        tty_gotoyx(offset,x1);
      colcnt=x1;
      if (blank) {
        g_array_append_val (coord, offset);
        g_array_append_val (coord, colcnt);
      }
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
      if (!blank)
        tty_gotoyx(offset,left_bound);
    }
    newline=FALSE;
    if (!*p) {
      if (blank)
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
        if (!blank)
          cell_data_setcolor (chunk_data);
        p+=tty_print_utf8(p,blank);
      }
      else {
        tty_setalloc_color ("brown", "blue", NULL, FALSE);
        if (!blank && colcnt>=right_bound) {
          tty_gotoyx(offset,right_bound);
          tty_print_char('>'); /*print on widget frame*/
        }
        else if(!blank && colcnt<left_bound) {
          tty_gotoyx(offset,left_bound-1);
          tty_print_char('<'); /*print on widget frame*/
        }
        p+=charlength_utf8(p);
      }
      colcnt++;
    }
  }
  message_assert (coord->len%3==0);
  return colcnt;
}

/*
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
*/

static int
get_chunk_horiz_shift(cell_data_t * chunk_data) {
  int horiz_shift;
  type_code_t type_code = chunk_data->type_code;
  if (
    type_code == TYPE_CODE_STRUCT ||
    type_code == TYPE_CODE_ARRAY  ||
    type_code == TYPE_CODE_UNION
  ) {
    horiz_shift=2;
  }
  else {
    horiz_shift=0;
  }
  return horiz_shift;
}

static int
print_chunks(GNode * chunk, int x1, int x2, int start_pos, int left_bound, int right_bound, Table *tab, int * rowcnt, gboolean blank) {
  message_assert (tab!=NULL);
  message_assert (CHUNK(chunk)!=NULL);
  if (CHUNK(chunk)->str) {
    return print_str_chunk (CHUNK(chunk),x1,x2,start_pos,left_bound,right_bound,tab,rowcnt, blank);
  }
  else {
    type_code_t type_code = CHUNK(chunk)->type_code;
    GArray * coord = CHUNK(chunk)->coord;
//    const char *str_begin=0, *str_end=0;
    int horiz_shift = get_chunk_horiz_shift (CHUNK(chunk));
    int start_pos_1;
    int offset;
    GNode *child = g_node_first_child (chunk);

//    if (type_code == TYPE_CODE_STRUCT || type_code == TYPE_CODE_UNION) {
//      str_begin="{\n";
//      str_end="}\n";
//    }
//    else if (type_code == TYPE_CODE_ARRAY) {
//      str_begin="[\n";
//      str_end="]\n";
//    }
    if (blank && coord->len>0)
      g_array_remove_range (coord, 0, coord->len);
    offset=ROW_OFFSET(tab,rowcnt[0]);
    if (blank) {
      g_array_append_val (coord, offset);
      g_array_append_val (coord, start_pos);
    }
//    if (str_begin) {
//      start_pos = print_str(str_begin,x1,x2,start_pos,left_bound,right_bound,tab,rowcnt);
//    }
    /*если chunk есть структура или массив, то начала печатается открывающая скобка с ПЕРЕНОСОМ строки
     *затем печатается тело структуры или массива, после чего печатается закрыающая скобка. Причем
     *тело печатается со сдвигом вправо.
    */
    start_pos_1 = (type_code == TYPE_CODE_STRUCT || type_code == TYPE_CODE_ARRAY || type_code == TYPE_CODE_UNION) ? (x1+horiz_shift) : (start_pos);
    while (child) {
      start_pos_1 = print_chunks (child,x1+horiz_shift,x2+horiz_shift,start_pos_1,left_bound,right_bound,tab,rowcnt,blank);
      child = g_node_next_sibling (child);
    }
  //  if (str_end)
  //    start_pos_1 = print_str(str_end,x1,x2,x1,left_bound,right_bound,tab,rowcnt);
    offset=ROW_OFFSET(tab,rowcnt[0]);
    start_pos = (type_code == TYPE_CODE_STRUCT || type_code == TYPE_CODE_ARRAY || type_code == TYPE_CODE_UNION) ? (x1) : (start_pos_1);
    if (blank) {
      g_array_append_val (coord, offset);
      g_array_append_val (coord, start_pos);
    }
  }

  return start_pos;
}

static void
table_draw_row (Table * tab, table_row *row, gboolean blank) {
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
  long * colstart;
  GNode ** columns;
  GNode  * column;
  int rowcnt;
  long max_rowcnt=1, x1, x2;
  long offset;
  message_assert (tab!=NULL);
  colstart = tab->colstart;
  columns = row->columns;
  if (blank)
    row->y1 = ROW_OFFSET(tab,0); /*y-коорд. последней строки + 1*/
  for(int i=0;i<tab->ncols;i++) {
    column = columns[i];
    x1 = i==0?colstart[i]:colstart[i]+1;
    x2 = colstart[i+1];
    rowcnt=0;
    offset=ROW_OFFSET(tab,rowcnt);
    if (!blank && offset>=TAB_TOP(tab) && offset<=TAB_BOTTOM(tab))
      tty_gotoyx(offset,x1);
    print_chunks (
      column,
      x1 - (row->offset[i]), /*координата самого левого символа ячейки таблицы*/
      x2 - (row->offset[i]), /*до этой координаты будет печататься столбец*/
      x1 - (row->offset[i]), /*позиция, с которой будет печататься первый chunk*/
      x1, /*ограничитель на печать слева*/
      x2, /*ограничитель на печать справа*/
      tab,
      &rowcnt,blank);
    rowcnt++;
    if(rowcnt>max_rowcnt)
      max_rowcnt=rowcnt;
  }
  if (blank) {
    tab->last_row_pos += max_rowcnt;
    row->y2 = ROW_OFFSET(tab,0);
  }
}
/*
static int
get_row_topbottom(Table * tab, table_row *row, int *t, int *b) {
  GNode ** columns = row->columns;
  GNode  * column;
  int top =0xffffff;
  int bottom=-0xffffff;
  int y_bottom,y_top;
  for(int i=0;i<tab->ncols;i++) {
    column = columns[i];
    GArray *coord = CHUNK(column)->coord;
    if (coord->len==4)
      y_bottom=g_array_index(coord,int,2);
    else
      y_bottom=g_array_index(coord,int,coord->len-3);
    y_top   =g_array_index(coord,int,0);
    if (top>y_top)
      top=y_top;
    if (bottom<y_bottom)
      bottom=y_bottom;
  }
  *t=top;
  *b=bottom;
}
*/

static void
table_draw(Table * tab) {
  /*see __table_draw*/
  __table_draw(tab,FALSE);
}

static void
table_compute_lengths(Table * tab) {
  /*see __table_draw*/
  Widget * w = WIDGET(tab->wtab);
  table_update_bounds(tab, w->y+2,w->x+1,w->lines-3,w->cols-2);
  __table_draw(tab,TRUE);
  tab->lengths_outdated=FALSE;
}


static void
__table_draw(Table * tab, gboolean blank) {
  /* Отрисовка таблицы разделяется на две части:
   * 1. Вычисление длин; 2. Непосредственная отрисовка на основле посчитанных длин.
   * Пункт 1. нужно выполнять только если таблица поменялась или отрисовывается впервые.
   * Например, при переключении вкладок таблицы остаются неизменными. Поэтому в случае
   * переключения вкладок для отрисовки таблицы достаточно вызывать __table_draw (tab,FALSE)
   * В случае, если таблицы была изменена, сначала вызывается __table_draw (tab,TRUE),
   * потом __table_draw (tab,FALSE)
   */
  GList *row;
  table_row *r;
  long offset;
  int rtop,rbottom,tt,tb;
  message_assert (tab!=NULL);
  row = tab->rows;
  tty_fill_region(tab->y,tab->x,tab->lines,tab->cols,' ');
  tab->last_row_pos = tab->y - tab->row_offset;
  tt=TAB_TOP(tab);
  tb=TAB_BOTTOM(tab);

  if (blank) {
    /*ничего не рисуется, только высчитывается длина*/
    while(row) {
      r = TABROW(row);
      table_draw_row (tab,r,blank);
      offset=ROW_OFFSET(tab,0);
      if (tab->draw_hline) {
        tab->last_row_pos++;
      }
      row = g_list_next (row);
    }
  }
  else {
    while(row) {
      r = TABROW(row);
      rtop=r->y1;
      rbottom=r->y2-1;
      //get_row_topbottom (tab,r,&top,&bottom);
      if ((rtop>=tt && rtop<=tb) || (rbottom>=tt && rbottom<=tb) || (rtop<=tt && rbottom>=tb)) {
        tab->last_row_pos=r->y1;
        tty_setcolor(EDITOR_NORMAL_COLOR);
        table_draw_row (tab,r,blank);
        tab->last_row_pos=r->y2;
        offset=ROW_OFFSET(tab,0);
        if (offset>TAB_TOP(tab) && offset<=TAB_BOTTOM(tab) && tab->draw_hline) {
          tty_setcolor(EDITOR_NORMAL_COLOR);
          tty_draw_hline(offset,tab->x,mc_tty_frm[MC_TTY_FRM_HORIZ],tab->cols);
          //tab->last_row_pos++;
        }
      }
      if (rtop>tb)
        break;
      row = g_list_next (row);
    }
  }

  if (!blank && tab->draw_vline) {
    tty_setcolor(EDITOR_NORMAL_COLOR);
    for(int i=1;i<tab->ncols;i++)
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
  message_assert (tab!=NULL);
  tab->lengths_outdated=TRUE;
  tab->x = x;
  tab->y = y;
  tab->lines = lines;
  tab->cols  = cols;
  tab->colstart[0] = x;
  table_update_colwidth(tab);
}


static Table *
table_new (const char *table_name, long ncols) {
  Table *tab;
  message_assert (ncols>=0);
  tab = g_new0(Table,1);
  tab->ncols=ncols;
  tab->nrows=0;
  tab->draw_vline = TRUE;
  tab->draw_hline = TRUE;
  tab->colstart = (long *)g_new0(long,ncols+1);
  tab->row_offset=0;
  table_set_colwidth_formula(tab,formula_eq_col);
  tab->hnodes = g_hash_table_new (g_direct_hash, g_direct_equal);
  tab->formula = formula_eq_col;
  tab->table_name = strdup(table_name);
  tab->lengths_outdated=TRUE;
  tab->selected_row=-1;
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
node_update_coord(GNode *node, int off) {
  GArray * coord = CHUNK(node)->coord;
  if (CHUNK(node)->str) {
    message_assert(coord->len>0);
    message_assert(coord->len%3==0);
    for (unsigned int idx=0;idx<coord->len;idx+=3) {
      //int y1 = g_array_index(coord,int,idx) - off;
      g_array_index(coord,int,idx) -= off;
    }
  }
  else {
    GNode *child;
    if (coord->len==4) {
      //int y1 = g_array_index(coord,int,0) - off;
      //int y2 = g_array_index(coord,int,2) - off;
      //g_array_insert_val(coord,0,y1);
      //g_array_insert_val(coord,2,y2);
      g_array_index(coord,int,0) -= off;
      g_array_index(coord,int,2) -= off;
    }
    child = g_node_first_child (node);
    while (child) {
      node_update_coord (child,off);
      child = g_node_next_sibling (child);
    }
  }
}

static void
table_update_coord(Table *tab, int off) {
  for (GList *row = tab->rows;row;row=g_list_next(row)) {
    GNode ** columns = TABROW(row)->columns;
    TABROW(row)->y1-=off;
    TABROW(row)->y2-=off;
    for(int i=0;i<tab->ncols;i++) {
      GNode *column = columns[i];
      node_update_coord(column,off);
    }
  }
}

static void
table_add_offset(Table *tab, int off) {
  int max_offset;
  int old_offset = tab->row_offset;
  int delta;
  if ( !TAB_FIRST_ROW(tab) ) {
    /*empty table*/
    return;
  }
  delta = tab->row_offset;
  max_offset = MAX(0,((TAB_LAST_ROW(tab)->y2 - TAB_FIRST_ROW(tab)->y1) - (TAB_BOTTOM(tab)-TAB_TOP(tab))));
  tab->row_offset += off;
  tab->row_offset = MAX(tab->row_offset, 0);
  tab->row_offset = MIN(tab->row_offset, max_offset);
  delta=tab->row_offset - old_offset;
  if (delta!=0)
    tab->redraw |= REDRAW_TAB;
  table_update_coord(tab,delta);
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
  long command;
  switch(msg) {
    case MSG_DRAW:
      tty_setcolor(EDITOR_NORMAL_COLOR);
      wtab->tab->redraw |= REDRAW_TAB;
      break;
    case MSG_KEY:
      command = keybind_lookup_keymap_command (wtab->tab->keymap, parm);
      switch (command) {
        case CK_Up:
          table_add_offset(wtab->tab,-1);
          break;
        case CK_Down:
          table_add_offset(wtab->tab,1);
          break;
        case CK_PageUp:
          /*Page Up*/
          /*Либо перемещаемся на треть таблицы к первой строке,
           * а если это смещение будет сильно большое, то сдвигаемся
           * на столько, что бы верхушка верхней строки была видна в верху таблицы*/
          table_add_offset(wtab->tab,-wtab->tab->lines/3);
          break;
        case CK_PageDown:
          /*Page Down*/
          table_add_offset(wtab->tab,wtab->tab->lines/3);
          break;
        case CK_MCGDB_Frame_up:
          mcgdb_shellcmd ("up");
          break;
        case CK_MCGDB_Frame_down:
          mcgdb_shellcmd ("down");
          break;
        case CK_MCGDB_Step:
          mcgdb_shellcmd ("step");
          break;
        case CK_MCGDB_Stepi:
          mcgdb_shellcmd ("stepi");
          break;
        case CK_MCGDB_Next:
          mcgdb_shellcmd ("next");
          break;
        case CK_MCGDB_Nexti:
          mcgdb_shellcmd ("nexti");
          break;
        case CK_MCGDB_Finish:
          mcgdb_shellcmd ("finish");
          break;
        case CK_MCGDB_Continue:
          mcgdb_shellcmd ("continue");
          break;
        case CK_MCGDB_Exit:
          mcgdb_shellcmd ("exit");
          break;
        case CK_MCGDB_Until:
          mcgdb_shellcmd ("until");
          break;

        default:
          break;
      }
      break;
    default:
      break;
  }
  if (NEED_REDRAW(wtab)) {
    wtable_draw(wtab);
  }
  widget_move (w, LINES, COLS);
  return handled;
}


static void
table_do_row_visible(Table *tab, int nrow) {
    table_row * selrow;
    int off;

    message_assert (tab!=NULL);
    message_assert (nrow < tab->nrows);

    selrow = TABROW(g_list_nth (tab->rows, nrow));
    if (selrow->y1 <= TAB_TOP(tab) &&  selrow->y2 >= TAB_TOP(tab)) {
      /* верхняя строка ячейки не видна, нижняя видна
       * Делаем, что бы верхняя была видна
       */
      off = selrow->y1 - (TAB_TOP(tab) + 1);
    }
    else if (selrow->y1 <= TAB_BOTTOM(tab) &&  selrow->y2 >= TAB_BOTTOM(tab)) {
      /*нижняя не видна, верхняя видна*/
      off = selrow->y2 - (TAB_BOTTOM(tab) - 1);
    }
    //else if (TAB_BOTTOM(tab)<=selrow->y1 || TAB_TOP(tab)>=selrow->y2) {
    else {
     /*ничего не видно, перемещаем ячейку в центр*/
     off = (selrow->y2 + selrow->y1)/2 - (TAB_BOTTOM(tab)+TAB_TOP(tab))/2;
    }
    table_add_offset (tab,off);
    tab->redraw=TRUE;
    //table_draw (tab, FALSE);
}

static void
wtable_do_row_visible(WTable *wtab, const char *tabname, gint id, int nrow) {
  Table *tab = wtable_get_exemplar(wtab,tabname,id);
  //Table *tab = wtable_get_table(wtab,tabname);
  tab->selected_row = nrow;
  tab->redraw = REDRAW_TAB;
  table_do_row_visible(tab,nrow);
}

void
wtable_do_row_visible_json(WTable *wtab, json_t *pkg) {
  const char *tabname=json_str (pkg,"table_name");
  gint id = json_integer_value (json_object_get (pkg, "id"));
  int nrow=json_int (pkg,"nrow");
  message_assert (tabname!=NULL);
  wtable_do_row_visible(wtab,tabname,id,nrow);
}



void
wtable_draw(WTable *wtab) {
  /*Fill widget space default color. If current table!=NULL, draw it.*/
  Table *tab = wtab->tab;
  tty_draw_box (WIDGET(wtab)->y+1, WIDGET(wtab)->x, WIDGET(wtab)->lines-1, WIDGET(wtab)->cols, FALSE);
  if (tab->lengths_outdated) {
    table_compute_lengths(tab);
  }
  if (tab->selected_row>=0) {
    table_do_row_visible(tab,tab->selected_row);
    tab->selected_row=-1;
  }

  table_add_offset (tab,0); /*make offset valid*/
  table_draw (tab);
  wtab->tab->redraw = REDRAW_NONE;
  tty_setcolor(EDITOR_NORMAL_COLOR);
  selbar_draw (wtab->selbar);
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
  int ncol;

  tab->mouse_down_x = event->x;
  tab->mouse_down_y = event->y;
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

  if (NEED_REDRAW(wtab)) {
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
      selbar->redraw = TRUE;
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
        wtable_set_tab(wtab,btn->text);
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


size_t
tty_print_utf8(const char *str, gboolean blank) {
  gunichar c;
  gchar *next_ch;
  if (!str || !*str)
    return 0;
  c = g_utf8_get_char_validated (str, -1);
  if (c == (gunichar) (-2) || c == (gunichar) (-1)) {
    if (!blank)
      tty_print_anychar('.');
    return 1;
  }
  if ((mc_global.utf8_display && g_unichar_isprint (c)) ||
      (!mc_global.utf8_display && is_printable (c)))
  {
      if (!blank)
        tty_print_anychar(c);
      next_ch = g_utf8_next_char (str);
      return next_ch - str;
  }
  else
  {
      if (!blank)
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



