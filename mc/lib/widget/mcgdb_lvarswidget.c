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


static cb_ret_t mcgdb_aux_dialog_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);
static cb_ret_t lvars_callback            (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);

static void mcgdb_aux_dialog_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event);
static void lvars_mouse_callback            (Widget * w, mouse_msg_t msg, mouse_event_t * event);

static Wlvars *lvars_new (int y, int x, int height, int width);

static lvars_row *  lvars_row_alloc(long ncols, va_list ap);
static void         lvars_row_destroy(lvars_row *row);
static void         lvars_tab_draw(const lvars_tab * tab, long row_offset);
static void         lvars_tab_update_bounds(lvars_tab * tab, long y, long x, long lines, long cols);
static lvars_tab *  lvars_tab_new (long ncols);
static void         lvars_tab_add_row (lvars_tab * tab, ...);
static void         lvars_tab_destroy(lvars_tab *tab);


static void
pkg_localvars(json_t *pkg, Wlvars *lvars) {
  tty_setcolor(EDITOR_NORMAL_COLOR);
  lvars_tab *tab = lvars->tab;
  json_t *localvars = json_object_get(pkg,"localvars");
  size_t size = json_array_size(localvars);
  for(size_t i=0;i<size;i++) {
    json_t * elem = json_array_get(localvars,i);
    lvars_tab_add_row (tab,
      json_object_get(elem,"name"),
      json_object_get(elem,"value"));
  }
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
          lvars->x=0;
          lvars->y=0;
          lvars->lines=LINES;
          lvars->cols =COLS/2;
          lvars_tab_update_bounds(lvars->tab,lvars->x+1,lvars->y+1,lvars->lines-1,lvars->cols-1);
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
    lvars->tab = lvars_tab_new(2);
    lvars_tab_add_colnames(lvars->tab,"name","value");
    lvars->x=0;
    lvars->y=0;
    lvars->lines=LINES;
    lvars->cols=COLS/2;
    lvars_tab_update_bounds(lvars->tab, lvars->x+1,lvars->y+1,lvars->lines-1,lvars->cols-1);
    return lvars;
}


static lvars_row *
lvars_row_alloc(long ncols, va_list ap) {
  lvars_row * row = g_new0 (lvars_row,1);
  row->ncols=ncols;
  row->columns = (char **)g_new0(char **, ncols);
  //va_start(ap,ncols);
  for (int col=0;col<ncols;col++) {
    char *val = va_arg(ap, char *);
    row->columns[col] = strdup(val);
  }
  //va_end(ap);
  return row;
}

static void
lvars_row_destroy(lvars_row *row) {
  
}


static void
lvars_tab_draw(const lvars_tab * tab, long row_offset) {
  GList *row = g_list_nth (tab->rows, row_offset);
  tty_setcolor(EDITOR_NORMAL_COLOR);
  tty_fill_region(tab->y,tab->x,tab->lines,tab->cols,' ');
  lvars_row *r;
  while(row) {
    r=(lvars_row *)row->data;
    tty_gotoyx(r->y1,1);
    tty_printf("%s",r->columns[0]);
    row = g_list_next(row);
  }
}

static void
lvars_tab_update_bounds(lvars_tab * tab, long y, long x, long lines, long cols) {
  GList *row = tab->rows;
  lvars_row *r;
  int cnt=y;
  while(row) {
    r=(lvars_row *)row->data;
    r->y1=cnt++;
    r->y2 = r->y1+1;
    row = g_list_next(row);
  }
}


static lvars_tab *
lvars_tab_new (long ncols) {
  lvars_tab *tab = g_new0(lvars_tab,1);
  tab->ncols=ncols;
  tab->nrows=0;
  return tab;
}

static void
lvars_tab_add_colnames (lvars_tab * tab, ...) {
  va_list ap;
  va_start (ap, tab);
  tab->colnames = lvars_row_alloc (ncols, ap);
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
      tty_fill_region(y+1,x+1,lines-1,cols-1,' ');
      tty_draw_box(y, x, lines, cols, FALSE);
      //tty_gotoyx(0,x+cols/2);
      //tty_print_char(mc_tty_frm[MC_TTY_FRM_TOPMIDDLE]);
      //tty_draw_vline(1,x+cols/2,mc_tty_frm[MC_TTY_FRM_VERT],lines-2);
      //tty_gotoyx(lines,x+cols/2);
      //tty_print_char(mc_tty_frm[MC_TTY_FRM_BOTTOMMIDDLE]);
      lvars_tab_draw (lvars->tab, 0);
      widget_move(w, LINES, COLS);
      //widget_move(w, 1000, 1000);
      break;
  }
  //tty_setcolor(EDITOR_NORMAL_COLOR);
  //widget_move(w, 0, 0);
  //tty_fill_region(0,0,100,100,' ');
  //tty_print_char(parm);

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
  Wlvars *lvars = lvars_new (0, 0, LINES, COLS/2);
  aux_dlg = dlg_create (FALSE, 0, 0, 0, 0, WPOS_FULLSCREEN, FALSE, NULL, mcgdb_aux_dialog_callback,
                    mcgdb_aux_dialog_mouse_callback, "[GDB]", NULL);
  add_widget (aux_dlg, lvars);
  dlg_run (aux_dlg);
  return 0;
}


