#include <config.h>

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

#define TAB_FIRST_ROW(tab) ((table_row *)(((tab)->rows)->data))
#define TAB_LAST_ROW(tab) ((table_row *)(     ((GList *)g_list_last ((tab)->rows))   ->data))


#define LVARS_X 0
#define LVARS_Y 1
#define LVARS_LINES(LINES) ((LINES)-1)
#define LVARS_COLS(COLS)  (COLS/2)

#define SELBAR_X 0
#define SELBAR_Y 0
#define SELBAR_LINES(LINES) 1
#define SELBAR_COLS(COLS) LVARS_COLS(COLS)

#define SELBAR_BUTTON(x) ((SelbarButton *)x)


static int VARS_AND_REGS_ID;

static cb_ret_t mcgdb_aux_dialog_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);
static cb_ret_t wtable_callback           (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);
static cb_ret_t selbar_callback           (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);

static void mcgdb_aux_dialog_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event);
static void wtable_mouse_callback           (Widget * w, mouse_msg_t msg, mouse_event_t * event);
static void selbar_mouse_callback           (Widget * w, mouse_msg_t msg, mouse_event_t * event);



static table_row *  table_row_alloc(long ncols, va_list ap);
static void         table_row_destroy(table_row *row);
static void         table_update_bounds(Table * tab, long y, long x, long lines, long cols);
static Table *      table_new (long ncols, ... );
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

static void         table_add_offset(Table *tab, int off);
WTable  *           find_wtable (WDialog *h);


typedef struct SelbarButton {
  char *text;
  void (*callback) (WDialog *h);
  gboolean selected;
  long x1;
  long x2;
} SelbarButton;

typedef struct Wselbar {
  Widget widget;
  long x;
  long y;
  long lines;
  long cols;
  GList *buttons;
  int selected_color;
  int normal_color;
  gboolean redraw;
} Wselbar;


Wselbar *find_selbar (WDialog *h);


static WTable  *wtable_new  (int y, int x, int height, int width);
static Wselbar *selbar_new (int y, int x, int height, int width);




static void
pkg_localvars(json_t *pkg, WTable *wtab) {
  Table *tab = wtab->tab;
  json_t *localvars = json_object_get(pkg,"localvars");
  size_t size = json_array_size(localvars);
  table_clear_rows(tab);
  tty_setcolor(EDITOR_NORMAL_COLOR);
  for(size_t i=0;i<size;i++) {
    json_t * elem = json_array_get(localvars,i);
    table_add_row (tab,
      json_string_value(json_object_get(elem,"name")),
      json_string_value(json_object_get(elem,"value"))
    );
  }
  table_update_colwidth(wtab->tab);
}

static void
mcgdb_aux_dialog_gdbevt (WDialog *h) {
  WTable *wtab;
  struct gdb_action * act = event_from_gdb;
  json_t *pkg = act->pkg;
  event_from_gdb=NULL;

  switch(act->command) {
    case MCGDB_LOCALVARS:
      wtab = dlg_find_by_id(h, VARS_AND_REGS_ID);
      if (wtab) {
        pkg_localvars(pkg,wtab);
      }
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
  WTable  *wtab;
  Wselbar *selbar;
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
        wtab = dlg_find_by_id(h, VARS_AND_REGS_ID);
        wtab->x      =LVARS_X;
        wtab->y      =LVARS_Y;
        wtab->lines  =LVARS_LINES(LINES);
        wtab->cols   =LVARS_COLS(COLS);
        wtable_update_bound(wtab);
        selbar = find_selbar (h);
        if (selbar) {
          selbar->cols = SELBAR_COLS(COLS);
        }
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
mcgdb_aux_dialog_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
  gboolean unhandled = TRUE;
  event->result.abort = unhandled;
}

static void
wtable_update_bound(WTable *wtab) {
  table_update_bounds(wtab->tab_registers, wtab->y+1,wtab->x+1,wtab->lines-2,wtab->cols-2);
  table_update_bounds(wtab->tab_localvars, wtab->y+1,wtab->x+1,wtab->lines-2,wtab->cols-2);
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
    VARS_AND_REGS_ID = w->id;
    widget_init (w, y, x, height, width, wtable_callback, wtable_mouse_callback);
    w->options |=   WOP_SELECTABLE;
    wtab->tab_localvars = table_new(2,"name","value");
    wtab->tab_registers = table_new(3,"","","");
    wtab->x=x;
    wtab->y=y;
    wtab->lines=height;
    wtab->cols=width;
    wtable_update_bound(wtab);
    table_set_colwidth_formula(wtab->tab_localvars, formula_adapt_col);
    table_set_colwidth_formula(wtab->tab_registers, formula_adapt_col);
    wtab->tab = wtab->tab_localvars;
    wtab->tab->redraw = REDRAW_NONE;
    return wtab;
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
formula_eq_col(const Table * tab, int ncol) {
  return (tab->cols/tab->ncols);
}

static int
formula_adapt_col(const Table * tab, int ncol) {
  int ncols = tab->ncols;
  int cols  = tab->cols;
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
    return max_width>0?max_width:max_avail_width;
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
  char *str,*p;
  long l, rowcnt, last_row_pos = tab->last_row_pos;
  long max_rowcnt=1, x1, x2;
  long y=tab->y;
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
  for(int i=0;i<ncols;i++) {
    tab->colstart[i+1] = tab->colstart[i] + tab->formula(tab,i);
  }
  tab->colstart[ncols] = x + cols;
}

static void
table_update_bounds(Table * tab, long y, long x, long lines, long cols) {
  GList *row = tab->rows;
  table_row *r;
  int cnt=y;
  tab->x = x;
  tab->y = y;
  tab->lines = lines;
  tab->cols  = cols;
  long ncols = tab->ncols;
  tab->colstart[0] = x;
  table_update_colwidth(tab);
}


static Table *
table_new (long ncols, ... ) {
  va_list ap;
  va_start (ap, ncols);
  Table *tab = g_new0(Table,1);
  tab->ncols=ncols;
  tab->nrows=0;
  tab->colnames = table_row_alloc(ncols, ap);
  tab->colstart = (long *)g_new0(long,ncols+1);
  tab->row_offset=0;
  table_set_colwidth_formula(tab,formula_adapt_col);
  va_end(ap);
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
  va_list ap;
  va_start (ap, tab);
  long ncols = tab->ncols;
  table_row *row = table_row_alloc (ncols, ap);
  tab->rows = g_list_append (tab->rows, row);
  tab->nrows++;
  va_end(ap);
}

static void
table_add_offset(Table *tab, int off) {
  int max_offset = MAX(0,((TAB_LAST_ROW(tab)->y2 - TAB_FIRST_ROW(tab)->y1) - (TAB_BOTTOM(tab)-TAB_TOP(tab))));
  int old_offset = tab->row_offset;
  tab->row_offset += off;
  tab->row_offset = MAX(tab->row_offset, 0);
  tab->row_offset = MIN(tab->row_offset, max_offset);
  if (tab->row_offset!=old_offset)
    tab->redraw |= REDRAW_TAB;
}

static cb_ret_t
wtable_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  cb_ret_t handled = MSG_HANDLED;
  WTable *wtab = (WTable *)w;
  long lines,cols,x,y, max_offset;
  Table *tab = wtab->tab;
  switch(msg) {
    case MSG_DRAW:
      tty_setcolor(EDITOR_NORMAL_COLOR);
      x     =   wtab->x;
      y     =   wtab->y;
      lines =   wtab->lines;
      cols  =   wtab->cols;
      tty_draw_box(y, x, lines, cols, FALSE);
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
    table_draw (wtab->tab);
    wtab->tab->redraw = REDRAW_NONE;
  }
  widget_move (w, LINES, COLS);
  return handled;
}

static void
wtable_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
  WTable *wtab = (WTable *)w;
  Table *tab = wtab->tab;

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
    table_draw (wtab->tab);
    wtab->tab->redraw = REDRAW_NONE;
  }
  widget_move (w, LINES, COLS);
}



WTable *
find_wtable (WDialog *h) {
  return find_widget_type(h,wtable_callback);
}

Wselbar *
find_selbar (WDialog *h) {
  return (Wselbar *) find_widget_type (h, selbar_callback);
}

/////////////////////////////////////////////////////////////


static void
selbar_draw (Wselbar *bar) {
  GList * button = bar->buttons;
  int cnt=0;
  bar->redraw=FALSE;
  tty_setcolor(EDITOR_NORMAL_COLOR);
  tty_fill_region(bar->y,bar->x,bar->lines,bar->cols,' ');
  tty_gotoyx(bar->y,bar->x);
  cnt++;
  tty_print_char(' ');
  while(button) {
    SelbarButton * btn = ((SelbarButton *)(button->data));
    btn->x1 = cnt;
    if (btn->selected)
      tty_setcolor(bar->selected_color);
    else
      tty_setcolor(bar->normal_color);
    const char *p = btn->text;
    if (cnt > bar->cols)
      break;
    while(*p) {
      tty_print_char(*p++);
      if (++cnt>=bar->cols)
        break;
    }
    btn->x2 = cnt;
    if (cnt<bar->cols) {
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
selbar_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  Wselbar *bar = (Wselbar *)w;
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
reset_selected (gpointer data, gpointer user_data) {
  SELBAR_BUTTON(data)->selected=FALSE;
}

static void
selbar_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
  int click_x;
  Wselbar *selbar = (Wselbar *)w;
  switch (msg) {
    case MSG_MOUSE_CLICK:
      click_x = event->x;
      GList * button = g_list_find_custom ( selbar->buttons, &click_x, find_button_in_list );
      if (button) {
        g_list_foreach (selbar->buttons, reset_selected, NULL);
        SELBAR_BUTTON(button->data)->selected=TRUE;
        selbar->redraw = TRUE;
        SELBAR_BUTTON(button->data)->callback(DIALOG(w->owner));
      }
      break;
    default:
      break;
  }
  if (selbar->redraw)
    selbar_draw (selbar);
}


static Wselbar *
selbar_new (int y, int x, int height, int width) {
    Wselbar *selbar;
    Widget *w;

    if (height <= 0)
        height = 1;

    selbar = g_new0 (Wselbar, 1);
    w = WIDGET (selbar);
    widget_init (w, y, x, height, width, selbar_callback, selbar_mouse_callback);
    w->options = 0; //|=   WOP_SELECTABLE;
    selbar->x=x;
    selbar->y=y;
    selbar->lines=height;
    selbar->cols=width;
    selbar->buttons=NULL;
    selbar->selected_color = tty_try_alloc_color_pair2 ("red", "black", "bold", FALSE);
    selbar->normal_color = tty_try_alloc_color_pair2 ("white", "cyan",   NULL, FALSE);
    return selbar;

}

void selbar_add_button(Wselbar *selbar, const char * text, void (*callback) (WDialog *h), gboolean selected) {
  SelbarButton *btn = g_new0 (SelbarButton,1);
  btn->text = strdup(text);
  btn->callback=callback;
  btn->selected = selected;
  selbar->buttons = g_list_append (selbar->buttons, (gpointer)btn);
}

static void
stub (WDialog *h) {}

static void
localvars_selected (WDialog *h) {
  WTable *wtab = dlg_find_by_id(h, VARS_AND_REGS_ID);
  wtab->tab = wtab->tab_localvars;
  table_draw(wtab->tab);
}

static void
registers_selected (WDialog *h) {
  WTable *wtab = dlg_find_by_id(h, VARS_AND_REGS_ID);
  wtab->tab = wtab->tab_registers;
  table_draw(wtab->tab);
}


int
mcgdb_aux_dlg(void) {
  WDialog *aux_dlg;
  WTable  *vars_and_regs = wtable_new (LVARS_Y, LVARS_X, LVARS_LINES(LINES), LVARS_COLS(COLS));
  Wselbar *bar = selbar_new  (SELBAR_Y,SELBAR_X, SELBAR_LINES(LINES), SELBAR_COLS(COLS));
  selbar_add_button (bar,"localvars",localvars_selected,TRUE);
  selbar_add_button (bar,"registers",registers_selected,FALSE);
  aux_dlg = dlg_create (FALSE, 0, 0, 0, 0, WPOS_FULLSCREEN, FALSE, NULL, mcgdb_aux_dialog_callback,
                    mcgdb_aux_dialog_mouse_callback, "[GDB]", NULL);
  add_widget (aux_dlg, vars_and_regs);
  add_widget (aux_dlg, bar);
  dlg_run (aux_dlg);
  return 0;
}


