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



static cb_ret_t mcgdb_aux_dialog_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);
static cb_ret_t wtable_callback           (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);
static cb_ret_t selbar_callback           (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);

static void mcgdb_aux_dialog_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event);
static void wtable_mouse_callback           (Widget * w, mouse_msg_t msg, mouse_event_t * event);
static void selbar_mouse_callback           (Widget * w, mouse_msg_t msg, mouse_event_t * event);



static table_row *  table_row_alloc(long ncols, va_list ap);
static void         table_row_destroy(table_row *row);
static void         table_update_bounds(Table * tab, long y, long x, long lines, long cols);
static Table *      table_new (long ncols, va_list ap);
static void         table_add_row (Table * tab, ...);
static void         table_destroy(Table *tab);
static void         table_clear_rows(Table * tab);
static void         table_draw(Table * tab);
static void         table_draw_row (Table * tab, table_row *r);
static void         table_draw_colnames (Table * tab, table_row *r);
static void         table_update_colwidth(Table * tab);
static void         table_set_colwidth_formula(Table * tab, int (*formula)(const Table * tab, int ncol));
static int          formula_eq_col(const Table * tab, int ncol);
static int          formula_adapt_col(const Table * tab, int ncol);
static void         wtable_update_bound(WTable *wtab);
static void         wtable_draw(WTable *wtab);

static void         table_add_offset(Table *tab, int off);
WTable  *           find_wtable (WDialog *h);


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
pkg_localvars(json_t *pkg, WTable *wtab) {
  json_t *localvars = json_object_get(pkg,"localvars");
  size_t size = json_array_size(localvars);
  Table *tab = wtable_get_table(wtab,"localvars");
  table_clear_rows(tab);
  tty_setcolor(EDITOR_NORMAL_COLOR);
  for(size_t i=0;i<size;i++) {
    json_t * elem = json_array_get(localvars,i);
    table_add_row (tab,
      json_string_value(json_object_get(elem,"name")),
      json_string_value(json_object_get(elem,"value"))
    );
  }
  table_update_colwidth(tab);
}

static char *
make_func_args (json_t * elem) {
  json_t *args = json_object_get(elem,"args");
  size_t size = json_array_size(args), psize=0;
  char *buf = malloc(1024);
  size_t bufsize=1024;
  psize+=snprintf(buf+psize,bufsize-psize,"%s (", //)
    json_string_value(json_object_get(elem,"func")));
  for(size_t i=0;i<size;i++) {
    json_t * arg = json_array_get(args,i);
    psize+=snprintf(buf+psize,bufsize-psize,"%s=%s,",
      json_string_value(json_object_get(arg,"name")),
      json_string_value(json_object_get(arg,"value"))
    );
  }
  if (size>0)
    psize-=1; /*remove last `,`*/
  psize+=snprintf(buf+psize,bufsize-psize,/*(*/")");
  if(size>0)
    buf[psize<bufsize?psize:bufsize-1]=0;
  return buf;
}

static char *
make_filename_line (json_t * elem) {
  char *ptr;
  const char *filename = json_string_value(json_object_get(elem,"filename"));
  if (strlen(filename)>0)
    asprintf(&ptr,"%s:%d",filename,json_integer_value(json_object_get(elem,"line")));
  else
    asprintf(&ptr,"unknown");
  return ptr;
}


static void
pkg_backtrace(json_t *pkg, WTable *wtab) {
  json_t *backtrace = json_object_get(pkg,"backtrace");
  size_t size = json_array_size(backtrace);
  Table *tab = wtable_get_table(wtab,"backtrace");
  table_clear_rows(tab);
  for(size_t i=0;i<size;i++) {
    json_t * elem = json_array_get(backtrace,i);
    char * func_args_str = make_func_args (elem);
    char * filename_line = make_filename_line (elem);
    char nframe[100];
    snprintf(nframe,sizeof(nframe),"%d",json_integer_value(json_object_get(elem,"nframe")));
    table_add_row (tab,
      nframe,
      func_args_str,
      filename_line
    );
    free(func_args_str);
    free(filename_line);
  }
  table_update_colwidth(tab);
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
      pkg_localvars(pkg,wtab);
      break;
    case MCGDB_BACKTRACE:
      wtab = (WTable *)dlg_find_by_id(h, BT_TH_TABLE_ID);
      pkg_backtrace(pkg,wtab);
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
wtable_add_table(WTable *wtab, const char *tabname, int ncols, ...) {
  Table *tab;
  va_list ap;
  va_start (ap, ncols);
  tab = table_new(ncols,ap);
  table_set_colwidth_formula(tab, formula_adapt_col);
  g_hash_table_insert ( wtab->tables, (gpointer) tabname, (gpointer) tab);
  selbar_add_button   ( wtab->selbar, tabname);
  va_end(ap);
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
table_row_alloc(long ncols, va_list ap) {
  table_row * row = g_new0 (table_row,1);
  row->ncols=ncols;
  row->columns = (char **)g_new0(char *, ncols);
  for (int col=0;col<ncols;col++) {
    char *val = va_arg(ap, char *);
    row->columns[col] = strdup(val);
  }
  return row;
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
}


static int
formula_eq_col(const Table * tab, __attribute__((unused)) int ncol) {
  return (tab->cols/tab->ncols);
}

static int
formula_adapt_col(const Table * tab, int ncol) {
  int ncols = tab->ncols;
  int width=0,max_width=0;
  int max_avail_width = formula_eq_col(tab,ncol);
  if(ncol<ncols) {
    GList * row = tab->rows;
    for(;row;row=g_list_next(row)) {
      width = strlen(((table_row *)row->data)->columns[ncol]);
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
table_draw_row (Table * tab, table_row *row) {
  long * colstart = tab->colstart;
  char ** columns = row->columns;
  char *p;
  long rowcnt;
  long max_rowcnt=1, x1, x2;
  long offset;
  row->y1 = ROW_OFFSET(tab,0);
  for(int i=0;i<tab->ncols;i++) {
    p = columns[i];
    x1 = i==0?colstart[i]:colstart[i]+1;
    x2 = colstart[i+1];
    rowcnt=0;
    offset=ROW_OFFSET(tab,rowcnt);
    if (offset>=TAB_TOP(tab) && offset<=TAB_BOTTOM(tab))
      tty_gotoyx(offset,x1);
    for(long colcnt=x1;*p;p++,colcnt++) {
      if(colcnt==x2) {
        rowcnt++;
        offset=ROW_OFFSET(tab,rowcnt);
        if (offset>=TAB_TOP(tab) && offset<=TAB_BOTTOM(tab))
          tty_gotoyx(offset,x1);
        colcnt=x1;
      }
      offset=ROW_OFFSET(tab,rowcnt);
      if (offset>=TAB_TOP(tab) && offset<=TAB_BOTTOM(tab))
        tty_print_char(*p);
    }
    rowcnt++;
    if(rowcnt>max_rowcnt)
      max_rowcnt=rowcnt;
  }
  tab->last_row_pos += max_rowcnt;
  row->y2 = ROW_OFFSET(tab,0);
}

static void
table_draw_colnames (Table * tab, table_row *r) {
  if (!r)
    return
  table_draw_row (tab,r);
}


static void
table_draw(Table * tab) {
  GList *row = tab->rows;
  table_row *r;
  long offset;
  tty_setcolor(EDITOR_NORMAL_COLOR);
  tty_fill_region(tab->y,tab->x,tab->lines,tab->cols,' ');
  tab->last_row_pos = tab->y - tab->row_offset;
  table_draw_colnames (tab,tab->colnames);

  while(row) {
    r = (table_row *)row->data;
    table_draw_row (tab,r);
    offset=ROW_OFFSET(tab,0);
    if (offset>TAB_TOP(tab) && offset<=TAB_BOTTOM(tab)) {
      tty_draw_hline(offset,tab->x,mc_tty_frm[MC_TTY_FRM_HORIZ],tab->cols);
    }
    tab->last_row_pos++;
    /*Делаем проход до самой последней строки что бы
     * вычислить координаты начала и конца каждой строки*/
    row = g_list_next (row);
  }
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
table_new (long ncols, va_list colnames) {
  Table *tab;
  tab = g_new0(Table,1);
  tab->ncols=ncols;
  tab->nrows=0;
  tab->colnames = table_row_alloc(ncols, colnames);
  tab->colstart = (long *)g_new0(long,ncols+1);
  tab->row_offset=0;
  table_set_colwidth_formula(tab,formula_adapt_col);
  return tab;
}

static void
table_destroy(Table *tab) {
  table_row_destroy(tab->colnames);
  g_free(tab->colstart);
  table_clear_rows(tab);
  g_free(tab);
}


static void
table_add_colnames (Table * tab, ...) {
  va_list ap;
  va_start (ap, tab);
  tab->colnames = table_row_alloc (tab->ncols, ap);
  va_end(ap);
}

static void
table_add_row (Table * tab, ...) {
  long ncols = tab->ncols;
  table_row *row;
  va_list ap;
  va_start (ap, tab);
  row = table_row_alloc (ncols, ap);
  tab->rows = g_list_append (tab->rows, row);
  tab->nrows++;
  va_end(ap);
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
  table_draw (wtab->tab);
  tty_draw_box (WIDGET(wtab)->y+1, WIDGET(wtab)->x, WIDGET(wtab)->lines-1, WIDGET(wtab)->cols, FALSE);
  selbar_draw (wtab->selbar);
  wtab->tab->redraw = REDRAW_NONE;
}

static void
wtable_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
  WTable *wtab = (WTable *)w;

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

  vars_regs_table = wtable_new (
    VARS_REGS_WIDGET_Y,
    VARS_REGS_WIDGET_X,
    VARS_REGS_WIDGET_LINES,
    VARS_REGS_WIDGET_COLS
  );
  wtable_add_table(vars_regs_table,"localvars",2,"name","value");
  wtable_add_table(vars_regs_table,"registers",3,"","","");
  wtable_set_current_table(vars_regs_table, "localvars");
  wtable_update_bound(vars_regs_table);

  bt_th_table = wtable_new (
    BT_TH_WIDGET_Y,
    BT_TH_WIDGET_X,
    BT_TH_WIDGET_LINES,
    BT_TH_WIDGET_COLS
  );
  wtable_add_table (bt_th_table,"backtrace",3,"","","");
  wtable_add_table (bt_th_table,"threads",3,"","","");
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


