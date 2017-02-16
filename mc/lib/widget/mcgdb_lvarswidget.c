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
//#include "lib/widget/listbox.h"

#include "lib/tty/tty.h"
#include "lib/skin.h"

#include <jansson.h>

#define ROW_OFFSET(tab,rowcnt) (((tab)->last_row_pos)+(rowcnt))
#define TAB_BOTTOM(tab) ((tab)->y+(tab)->lines - 1)
#define TAB_TOP(tab) ((tab)->y)


#define FIRST_ROW_VISIBLE(tab) (((lvars_row *)((tab)->rows->data))->y1>=TAB_TOP(tab))
#define LAST_ROW_VISIBLE(tab)  (((lvars_row *)(g_list_last ((tab)->rows)->data))->y2<TAB_BOTTOM(tab))


#define LVARS_X 0
#define LVARS_Y 0
#define LVARS_LINES(LINES) (LINES)
#define LVARS_COLS(COLS)  (COLS/2)

static cb_ret_t mcgdb_aux_dialog_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);
static cb_ret_t lvars_callback            (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);

static void mcgdb_aux_dialog_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event);
static void lvars_mouse_callback            (Widget * w, mouse_msg_t msg, mouse_event_t * event);

static Wlvars *lvars_new (int y, int x, int height, int width);

static lvars_row *  lvars_row_alloc(long ncols, va_list ap);
static void         lvars_row_destroy(lvars_row *row);
static void         lvars_tab_update_bounds(lvars_tab * tab, long y, long x, long lines, long cols);
static lvars_tab *  lvars_tab_new (long ncols, ... );
static void         lvars_tab_add_row (lvars_tab * tab, ...);
static void         lvars_tab_destroy(lvars_tab *tab);
static void         lvars_tab_clear_rows(lvars_tab * tab);
static void         lvars_tab_draw(lvars_tab * tab);
static void         lvars_tab_draw_row (lvars_tab * tab, lvars_row *r);
static void         lvars_tab_draw_colnames (lvars_tab * tab, lvars_row *r);
static void         lvars_tab_update_colwidth(lvars_tab * tab);
static void         lvars_tab_set_colwidth_formula(lvars_tab * tab, int (*formula)(const lvars_tab * tab, int ncol));
static int          formula_eq_col(const lvars_tab * tab, int ncol);
static int          formula_adapt_col(const lvars_tab * tab, int ncol);

static void
pkg_localvars(json_t *pkg, Wlvars *lvars) {
  lvars_tab *tab = lvars->tab;
  json_t *localvars = json_object_get(pkg,"localvars");
  size_t size = json_array_size(localvars);
  lvars_tab_clear_rows(tab);
  tty_setcolor(EDITOR_NORMAL_COLOR);
  for(size_t i=0;i<size;i++) {
    json_t * elem = json_array_get(localvars,i);
    lvars_tab_add_row (tab,
      json_string_value(json_object_get(elem,"name")),
      json_string_value(json_object_get(elem,"value"))
    );
  }
  lvars_tab_update_colwidth(lvars->tab);
  //lvars_tab_update_bounds(lvars->tab, lvars->x+1,lvars->y+1,lvars->lines-2,lvars->cols-2);
}

static void
mcgdb_aux_dialog_gdbevt (WDialog *h) {
  Wlvars *lvars;
  struct gdb_action * act = event_from_gdb;
  json_t *pkg = act->pkg;
  event_from_gdb=NULL;

  switch(act->command) {
    case MCGDB_LOCALVARS:
      lvars = find_lvars(h);
      if (lvars) {
        pkg_localvars(pkg,lvars);
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
  Wlvars *lvars;
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
        lvars = find_lvars(h);
        if (lvars) {
          lvars->x      =LVARS_X;
          lvars->y      =LVARS_Y;
          lvars->lines  =LVARS_LINES(LINES);
          lvars->cols   =LVARS_COLS(COLS);
          lvars_tab_update_bounds(lvars->tab,lvars->x+1,lvars->y+1,lvars->lines-2,lvars->cols-2);
        }
        return MSG_HANDLED;
      }
    default:
      {
        return dlg_default_callback (w, sender, msg, parm, data);
      }
  }
}


static void
mcgdb_aux_dialog_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
  gboolean unhandled = TRUE;
  event->result.abort = unhandled;
}



static Wlvars *
lvars_new (int y, int x, int height, int width)
{
    Wlvars *lvars;
    Widget *w;

    if (height <= 0)
        height = 1;

    lvars = g_new (Wlvars, 1);
    w = WIDGET (lvars);
    widget_init (w, y, x, height, width, lvars_callback, lvars_mouse_callback);
    w->options |=   WOP_SELECTABLE;
    lvars->tab = lvars_tab_new(2,"name","value");
    lvars->x=x;
    lvars->y=y;
    lvars->lines=height;
    lvars->cols=width;
    lvars->redraw = REDRAW_NONE;
    lvars_tab_update_bounds(lvars->tab, lvars->x+1,lvars->y+1,lvars->lines-2,lvars->cols-2);
    lvars_tab_set_colwidth_formula(lvars->tab, formula_adapt_col);
    return lvars;
}


static lvars_row *
lvars_row_alloc(long ncols, va_list ap) {
  lvars_row * row = g_new0 (lvars_row,1);
  row->ncols=ncols;
  row->columns = (char **)g_new0(char *, ncols);
  for (int col=0;col<ncols;col++) {
    char *val = va_arg(ap, char *);
    row->columns[col] = strdup(val);
  }
  return row;
}

static void
lvars_row_destroy(lvars_row *row) {
  
}

static void
lvars_row_destroy_g(gpointer data) {
  lvars_row_destroy ((lvars_row *)data);
}


static void
lvars_tab_clear_rows(lvars_tab * tab) {
  g_list_free_full (tab->rows,lvars_row_destroy_g);
  tab->rows = NULL;
}


static int
formula_eq_col(const lvars_tab * tab, int ncol) {
  return (tab->cols/tab->ncols);
}

static int
formula_adapt_col(const lvars_tab * tab, int ncol) {
  int ncols = tab->ncols;
  int cols  = tab->cols;
  int width=0,max_width=0;
  int max_avail_width = formula_eq_col(tab,ncol);
  if(ncol<ncols) {
    GList * row = tab->rows;
    for(;row;row=g_list_next(row)) {
      width = strlen(((lvars_row *)row->data)->columns[ncol]);
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
lvars_tab_set_colwidth_formula(lvars_tab * tab, int (*formula)(const lvars_tab * tab, int ncol)) {
  tab->formula = formula;
}


static void
lvars_tab_draw_row (lvars_tab * tab, lvars_row *row) {
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
    if (offset>=y)
      tty_gotoyx(offset,x1);
    for(long colcnt=x1;*p;p++,colcnt++) {
      if(colcnt==x2) {
        rowcnt++;
        offset=ROW_OFFSET(tab,rowcnt);
        if (offset>=y)
          tty_gotoyx(offset,x1);
        colcnt=x1;
      }
      offset=ROW_OFFSET(tab,rowcnt);
      if(offset  > TAB_BOTTOM(tab))
        break;
      if (offset>=TAB_TOP(tab))
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
lvars_tab_draw_colnames (lvars_tab * tab, lvars_row *r) {
  if (!r)
    return
  lvars_tab_draw_row (tab,r);
}


static void
lvars_tab_draw(lvars_tab * tab) {
  GList *row = tab->rows;
  tty_setcolor(EDITOR_NORMAL_COLOR);
  tty_fill_region(tab->y,tab->x,tab->lines,tab->cols,' ');
  lvars_row *r;
  long offset;
  tab->last_row_pos = tab->y - tab->row_offset;
  lvars_tab_draw_colnames (tab,tab->colnames);

  while(row) {
    r = (lvars_row *)row->data;
    lvars_tab_draw_row (tab,r);
    offset=ROW_OFFSET(tab,0);
    if (offset>tab->y && offset<tab->y+tab->lines) {
      tty_draw_hline(offset,tab->x,mc_tty_frm[MC_TTY_FRM_HORIZ],tab->cols);
      tab->last_row_pos++;
    }
    if(ROW_OFFSET(tab,0)>tab->y+tab->lines) {
      /*допечатали до самой последней строки*/
      break;
    }
    row = g_list_next (row);
  }
  for(int i=1;i<tab->ncols;i++) {
    tty_draw_vline(tab->y,tab->colstart[i],mc_tty_frm[MC_TTY_FRM_VERT],tab->lines);
  }
}

static void
lvars_tab_update_colwidth(lvars_tab * tab) {
  long x        = tab->x;
  long ncols    = tab->ncols;
  long cols     = tab->cols;
  for(int i=0;i<ncols;i++) {
    tab->colstart[i+1] = tab->colstart[i] + tab->formula(tab,i);
  }
  tab->colstart[ncols] = x + cols;
}

static void
lvars_tab_update_bounds(lvars_tab * tab, long y, long x, long lines, long cols) {
  GList *row = tab->rows;
  lvars_row *r;
  int cnt=y;
  tab->x = x;
  tab->y = y;
  tab->lines = lines;
  tab->cols  = cols;
  long ncols = tab->ncols;
  tab->colstart[0] = x;
  lvars_tab_update_colwidth(tab);
}


static lvars_tab *
lvars_tab_new (long ncols, ... ) {
  va_list ap;
  va_start (ap, ncols);
  lvars_tab *tab = g_new0(lvars_tab,1);
  tab->ncols=ncols;
  tab->nrows=0;
  tab->colnames = lvars_row_alloc(ncols, ap);
  tab->colstart = (long *)g_new(long,ncols+1);
  tab->row_offset=0;
  lvars_tab_set_colwidth_formula(tab,formula_adapt_col);
  va_end(ap);
  return tab;
}

static void
lvars_tab_add_colnames (lvars_tab * tab, ...) {
  va_list ap;
  va_start (ap, tab);
  tab->colnames = lvars_row_alloc (tab->ncols, ap);
  va_end(ap);
}

static void
lvars_tab_add_row (lvars_tab * tab, ...) {
  va_list ap;
  va_start (ap, tab);
  long ncols = tab->ncols;
  lvars_row *row = lvars_row_alloc (ncols, ap);
  tab->rows = g_list_append (tab->rows, row);
  tab->nrows++;
  va_end(ap);
}

static void
lvars_tab_destroy(lvars_tab *tab) {
  
}

static cb_ret_t
lvars_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  cb_ret_t handled = MSG_HANDLED;
  Wlvars *lvars = (Wlvars *)w;
  long lines,cols,x,y;
  switch(msg) {
    case MSG_DRAW:
      tty_setcolor(EDITOR_NORMAL_COLOR);
      x     =   lvars->x;
      y     =   lvars->y;
      lines =   lvars->lines;
      cols  =   lvars->cols;
      tty_draw_box(y, x, lines, cols, FALSE);
      lvars->redraw |= REDRAW_TAB;
      break;
    case MSG_KEY:
      switch (parm) {
        case KEY_UP:
          if (!FIRST_ROW_VISIBLE(lvars->tab)) {
            lvars->tab->row_offset-=1;
            lvars->redraw |= REDRAW_TAB;
          }
          break;
        case KEY_DOWN:
          if (!LAST_ROW_VISIBLE(lvars->tab)) {
            lvars->tab->row_offset+=1;
            lvars->redraw |= REDRAW_TAB;
          }
          break;
        case KEY_NPAGE:
          /*Page Up*/
          lvars->tab->row_offset-=lvars->tab->lines/2;
          lvars->redraw |= REDRAW_TAB;
          break;
        case KEY_PPAGE:
          /*Page Up*/
          lvars->tab->row_offset+=lvars->tab->lines/2;
          lvars->redraw |= REDRAW_TAB;
          break;
      }
      break;
  }
  if (lvars->redraw & REDRAW_TAB) {
    lvars_tab_draw (lvars->tab);
    lvars->redraw = REDRAW_NONE;
  }
  widget_move (w, LINES, COLS);
  return handled;
}

static void
lvars_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
}


Wlvars *
find_lvars (WDialog *h) {
  return (Wlvars *) find_widget_type (h, lvars_callback);
}

int
mcgdb_aux_dlg(void) {
  WDialog *aux_dlg;
  Wlvars *lvars = lvars_new (LVARS_X, LVARS_Y, LVARS_LINES(LINES), LVARS_COLS(COLS));
  aux_dlg = dlg_create (FALSE, 0, 0, 0, 0, WPOS_FULLSCREEN, FALSE, NULL, mcgdb_aux_dialog_callback,
                    mcgdb_aux_dialog_mouse_callback, "[GDB]", NULL);
  add_widget (aux_dlg, lvars);
  dlg_run (aux_dlg);
  return 0;
}


