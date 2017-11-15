#include <config.h>

#include "lib/global.h"
#include <strings.h>
#include "src/keybind-defaults.h" /*bpw_map*/
#include "src/mcgdb.h"
#include "lib/widget/wblock.h"
#include "lib/skin.h" /*EDITOR_NORMAL_COLOR*/
#include "lib/tty/tty.h"

#define WBMAIN(w) ((WBlockMain *)(w))

#define WBM_WBLOCK_DRAW(wbm,do_draw) \
  WBLOCK_DRAW ( \
    wbm->wb, \
    WIDGET(wbm)->y-wbm->offset, \
    WIDGET(wbm)->x, \
    WIDGET(wbm)->y, \
    WIDGET(wbm)->x, \
    WIDGET(wbm)->lines, \
    WIDGET(wbm)->cols, \
    do_draw);

#define WBM_UPDATE_COORDS(wbm) WBM_WBLOCK_DRAW(wbm,FALSE)

#define WBM_REDRAW(wbm) \
  do { \
  tty_setcolor (BUTTONBAR_BUTTON_COLOR);\
  tty_fill_region ( \
    WIDGET(wbm)->y, \
    WIDGET(wbm)->x, \
    MIN (wbm->wb->lines,WIDGET(wbm)->lines), \
    MIN (wbm->wb->cols,WIDGET(wbm)->cols), \
    ' '); \
  WBM_WBLOCK_DRAW(wbm,TRUE); \
} while (0)


typedef struct WBlockMain {
  Widget w;
  WBlock *wb;
  pos_callback_t calcpos;
  int offset;
  WBlock *selected_widget;
} WBlockMain;

static WBlockMain * wbm_new (WBlock *wb, pos_callback_t calcpos);
static void wbm_cleanup (WBlockMain * wbm);

static void
wbm_normalize_offset (WBlockMain *wbm) {
  wbm->offset = MIN(MAX(wbm->offset,0),MAX(wbm->wb->lines - WIDGET(wbm)->lines,0));
}

static gboolean
wbm_mouse (WBlockMain *wbm, mouse_msg_t msg, mouse_event_t * event) {
  WBlock *c = wblock_get_widget_yx (wbm->wb, event->y, event->x); //most depth widget
  while (c) {
    if (c->mouse) {
      gboolean res;
      event->x-=c->x;
      event->y-=c->y;
      res = WBLOCK_MOUSE (c, msg, event);
      event->x+=c->x;
      event->y+=c->y;
      if (res) {
        wbm->selected_widget = c;
        return TRUE;
      }
    }
    c = c->parent;
  }
  wbm->selected_widget = NULL;
  return FALSE;
}


static void
wbm_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
  WBlockMain *wbm = WBMAIN(w);
  int saved_offset = wbm->offset;
  gboolean res, redraw;
  event->y-=w->y;
  event->x-=w->x;
  res = wbm_mouse (wbm, msg, event);
  event->y+=w->y;
  event->x+=w->x;
  if (res)
    return;

  switch (msg) {
    case MSG_MOUSE_SCROLL_UP:
        wbm->offset-=2;
        wbm_normalize_offset (wbm);
        break;
    case MSG_MOUSE_SCROLL_DOWN:
        wbm->offset+=2;
        wbm_normalize_offset (wbm);
        break;
    default:
        break;
  }

  redraw = saved_offset!=wbm->offset;
  if (redraw) {
    WBM_UPDATE_COORDS (wbm);
    WBM_REDRAW (wbm);
  }
}

static cb_ret_t
wbm_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  int command;
  gboolean redraw;
  cb_ret_t handled = MSG_NOT_HANDLED;
  WBlockMain *wbm = WBMAIN(w);
  int saved_offset = wbm->offset;
  switch (msg) {
    case MSG_RESIZE:
    case MSG_INIT:
      {
        int y,x,lines,cols;
        WBMAIN(w)->calcpos(&y,&x,&lines,&cols);
        w->x=x;
        w->y=y;
        w->lines=lines;
        w->cols=cols;
      }
      WBM_UPDATE_COORDS (wbm);
      wbm_normalize_offset (wbm);
      break;
    case MSG_DRAW:
      WBM_REDRAW (wbm);
      return MSG_HANDLED;
    case MSG_KEY:
      if (wbm->selected_widget && WBLOCK_KEY (wbm->selected_widget, parm))
        return MSG_HANDLED;
      break;
    default:
      break;
  }

  switch (msg) {
    case MSG_KEY:
      command = keybind_lookup_keymap_command (mcgdb_bpw_map, parm);
      switch (command) {
        case CK_Up:
          wbm->offset-=1;
          handled=MSG_HANDLED;
          break;
        case CK_Down:
          wbm->offset+=1;
          handled=MSG_HANDLED;
          break;
        case CK_PageUp:
          wbm->offset-=w->lines/3;
          handled=MSG_HANDLED;
          break;
        case CK_PageDown:
          wbm->offset+=w->lines/3;
          handled=MSG_HANDLED;
          break;
        default:
          break;
      }
      wbm_normalize_offset (wbm);
      redraw = saved_offset!=wbm->offset;
      if (redraw) {
        WBM_UPDATE_COORDS (wbm);
        WBM_REDRAW (wbm);
      }
      break;
    default:
      break;
  }

  return handled;
}

static WBlockMain *
wbm_new (WBlock *wb, pos_callback_t calcpos) {
  WBlockMain *wbm = g_new0 (WBlockMain, 1);
  Widget *w;
  wbm->wb = wb;
  wbm->calcpos = calcpos;
  w = WIDGET(wbm);
  widget_init (w, 1, 1, 1, 1, wbm_callback, wbm_mouse_callback);
  widget_set_options (w, WOP_SELECTABLE, TRUE);
  return wbm;
}

static void
wbm_cleanup (WBlockMain * wbm) {

}

WBlock *
wblock_get_widget_yx (WBlock *wb, int y, int x) {
  if (!YX_IN_WIDGET (wb,y,x))
    return NULL;

  for (GList *l=g_list_last (wb->widgets);l;l=l->prev) {
    WBlock *c = WBLOCK (l->data);
    if (YX_IN_WIDGET (c,y,x)) {
      return wblock_get_widget_yx (c, y, x);
    }
  }

  return wb;
}


void
wblock_dfl_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  int y_line_max=y0,
      x_line_max=x0;
  int y_widget=y0, x_widget=x0;

  for (GList *l=wb->widgets;l;l=l->next) {
    //int draw_x, draw_y, draw_lines, draw_cols;
    WBlock *c = WBLOCK (l->data);

    if (c->style.layout==LAYOUT_BLOCK) {
      y_widget = y_line_max;
      x_widget = x0;
    }

    x_widget+=c->style.margin.left;
    y_widget+=c->style.margin.top;

    if (!do_draw) {
      c->y = y_widget;
      c->x = x_widget;
      c->lines=-1;
      c->cols=-1;
    }
    WBLOCK_DRAW (c, y_widget, x_widget, y, x, lines, cols, do_draw);
    if (!do_draw) {
      message_assert (c->lines>=0);
      message_assert (c->cols>=0);
      switch (c->style.width_type) {
        case WIDTH_MAX:
          c->cols = MAX (c->cols, x + cols - x_widget - c->style.margin.right);
          break;
        default:
          break;
      }
    }
    y_line_max = MAX(y_line_max, y_widget+c->lines+c->style.margin.bottom);
    x_line_max = MAX(x_line_max, x_widget+c->cols+c->style.margin.right);

    if (c->style.layout==LAYOUT_BLOCK) {
      y_widget = y_line_max;
      x_widget = x0;
    }
    else if (c->style.layout==LAYOUT_INLINE) {
      x_widget+=c->cols+c->style.margin.right;
    }
  }

  if (!do_draw) {
    wb->lines = y_line_max - y0;
    wb->cols = x_line_max - x0;
  }
}


void
wblock_dfl_destroy (WBlock *wb) {
  for (GList *l=wb->widgets;l!=NULL;l=l->next) {
    WBLOCK_DESTROY (WBLOCK (l->data));
  }
  g_list_free (wb->widgets);
  g_free (wb->wdata);
}

void
wblock_init (
  WBlock *wb,
  wblock_mouse_cb_t   mouse,
  wblock_key_cb_t     key,
  wblock_destroy_cb_t destroy,
  wblock_draw_cb_t    draw,
  gpointer wdata)
{
  bzero (wb, sizeof (WBlock));
  wb->destroy   = destroy   ? destroy   : wblock_dfl_destroy;
  wb->draw      = draw      ? draw      : wblock_dfl_draw;
  wb->key       = key;
  wb->mouse     = mouse;
  wb->wdata     = wdata;
}

WBlock *
wblock_new (
  wblock_mouse_cb_t   mouse,
  wblock_key_cb_t     key,
  wblock_destroy_cb_t destroy,
  wblock_draw_cb_t    draw,
  gpointer wdata)
{
  WBlock *wb = g_new0 (WBlock,1);
  wblock_init (wb, mouse, key, destroy, draw, wdata);
  return wb;
}


void
wblock_add_widget (WBlock * wb, WBlock * widget) {
  wb->widgets = g_list_append (wb->widgets, widget);
  widget->parent = wb;
}


static cb_ret_t
wblock_dlg_default_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data)
{
    WBlockMain *wbm =  WBMAIN (DIALOG (w)->widgets->data);
    return WIDGET (wbm)->callback (WIDGET (wbm), sender, msg, parm, data);
}


int
wblock_run (WBlock * wb, pos_callback_t calcpos) {
  WDialog *dlg;
  WBlockMain * wbm = wbm_new (wb, calcpos);
  int return_val;
  dlg = dlg_create (TRUE, 0, 0, 0, 0, WPOS_KEEP_DEFAULT, FALSE, NULL, wblock_dlg_default_callback,
                    NULL, "[wblock]", NULL);

  add_widget (dlg, wbm);
  return_val = dlg_run (dlg);

  wbm_cleanup (wbm);
  dlg_destroy (dlg);


  return return_val;
}

