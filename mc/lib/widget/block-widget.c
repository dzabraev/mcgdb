#include "config.h"
#include "lib/widget/block-widget.h"

#define WBMAIN(w) ((WBlockMain *)(w))

typedef struct WBlockMain {
  Widget w;
  WBlock *wb;
  pos_callback_t calcpos;
  int offset;
  int lines_total;
} WBlockMain;


static void
wbm_normalize_offset (WBlockMain *wbm) {
  wbm->offset = MIN(MAX(wbm->offset,0),MAX(wbm->lines_total - WIDGET(wbm)->lines,0));
}

static void
wbm_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
  WBlockMain *wbm = WBMAIN(w);
  int saved_offset = wbm->offset;
  if (WBLOCK_MOUSE (wbm->wb, msg, event))
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
  if (redraw)
    WBLOCK_CALLBACK (wbm->wb,MSG_DRAW,0,NULL);
}

static cb_ret_t
wbm_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  int command;
  cb_ret_t handled = MSG_NOT_HANDLED;
  WBlockMain *wbm = WBMAIN(w);
  WBlcok *wb = wbm->wb;
  int saved_offset = wbm->offset;
  switch (msg) {
    case MSG_RESIZE:
    case MSG_INIT:
      WBMAIN(w)->calcpos(w);
      WBLOCK_CALCSIZE (wb,w->y,w->x,w->y,w->x,w->lines,w->cols);
      break;
    case MSG_DRAW:
      WBLOCK_DRAW (wb,w->y-wbm->offset,w->x,w->y,w->x,w->lines,w->cols);
      return MSG_HANDLED;
    case MSG_KEY:
      if (WBLOCK_KEY (wb,parm))
        return MSG_HANDLED;
    default:
      break;
  }

  switch (msg) {
    case MSG_KEY:
      command = keybind_lookup_keymap_command (mcgdb_bpw_map, parm);
      switch (command) {
        case CK_Up:
          bpw->offset-=1;
          handled=MSG_HANDLED;
          break;
        case CK_Down:
          bpw->offset+=1;
          handled=MSG_HANDLED;
          break;
        case CK_PageUp:
          bpw->offset-=w->lines/3;
          handled=MSG_HANDLED;
          break;
        case CK_PageDown:
          bpw->offset+=w->lines/3;
          handled=MSG_HANDLED;
          break;
        default:
          break;
      }
      wbm_normalize_offset (wbm);
      redraw = saved_offset!=wbm->offset;
      if (redraw)
        WBLOCK_DRAW (wb,w->y-wbm->offset,w->x,w->y,w->x,w->lines,w->cols);
      break;
    default:
      break;
  }

  return handled;
}

WBlockMain *
wbm_new (WBlock *wb, pos_callback_t calcpos) {
  WBlockMain *wbm = g_new0 (WBlockMain);
  wb_main->wb = wb;
  wb_main->calcpos = calcpos;
  Widget *w = WIDGET(wbm)
  widget_init (w, 1, 1, 1, 1, wbm_callback, wbm_mouse_callback);
  widget_set_options (w, WOP_SELECTABLE, TRUE);
  return wbm;
}

WBlock *
wblock_get_widget_yx (WBlock *wb, int y, int x) {

}

gboolead
wblock_dfl_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event) {
  WBlock *wb_child = wblock_get_widget_yx (wb, event->y, event->x);
  if (wb_child && wb_child->mouse_callback) {
    if (WBLOCK_MOUSE (wb_child, msg, event)) {
      wb->selected_widget = wb_child;
      return TRUE;
    }
    else {
      wb->selected_widget = NULL;
      return FALSE;
    }
  }
}

void __wblock_dfl_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean draw) {

}

void
wblock_dfl_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols) {
  int y1=y0,x1=x0;
  int line_bottom=y0;
  for (GList *l=wb->widgets;l;l=l->next) {
    WBlock *c = WBLOCK (l);
    style = c->style;
    int x2,y2;
    if (style.layout==LAYOUT_BLOCK) {
      x2 = x0+style.marign.left;
      y2 = line_bottom+style.marign.left;
    }
    else if (style.layout==LAYOUT_INLINE) {
      x1 = MAX(x1,c->x+c->lines+style.margin.right);
    }
    WBLOCK_DRAW (c, y2, x2, y, x, lines, cols);
    if (style.layout==LAYOUT_BLOCK) {
      y1 = MAX(c->y+c->lines+style.marin.bottom,y1);
      x1 = x0;
    }
    else if (style.layout==LAYOUT_INLINE) {
      x1 = MAX(x1,c->x+c->lines+style.margin.right);
    }
  }
}

void
wblock_dfl_calc_size (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols) {
  wb->x=x+cols;
  wb->y=y+lines
  wb->cols=0;
  wb->lines=0;
  __wblock_dfl_draw (wb,y0,x0,y,x,lines,cols,FALSE);
  for (GList *l=wb->widgets;l;l=l->next) {
    WBlock *c = WBLOCK (l);

    wb->x = MIN(c->x,wb->x);
    wb->y = MIN(c->x,wb->x);
  }
}

gboolean
wblock_dfl_key (WBlock *wb, int parm) {
  if (wb->selected_widget)
    return WBLOCK_KEY (wb->selected_widget, parm);
  else
    return FALSE;
}

void
wblock_dfl_destroy (WBlock *wb) {
  for (GList *l=wb->widgets;l!=NULL;l=l->next) {
    WBLOCK_DESTROY (WBLOCK (l));
  }
  g_list_free (wb->widgets);
}

WBlock *
wblock_new (
  wblock_mouse_cb_t mouse,
  wblock_key_cb_t key,
  wblock_destroy_cb_t destroy,
  wblock_draw_cb_t draw,
  wblock_calc_size_cb_t calc_size,
  gpointer wdata)
{
  WBlock *wb = g_new0 (WBlock,1);
  wb->destroy   = destroy   ? destroy   : wblock_dfl_default;
  wb->draw      = draw      ? draw      : wblock_dfl_draw;
  wb->key       = key       ? key       : wblock_dfl_key;
  wb->calc_size = calc_size ? calc_size : wblock_dfl_calc_size;
  wb->mouse     = mouse     ? mouse     : wblock_dfl_mouse;
  wv->wdata = wdata;
  return wb;
}


void
wblock_add_widget (WBlock * wb, WBlock * widget) {
  wb->widgets = g_list_append (wb->widgets, widget);
  widget->parent = wb;
}


int
wblock_run (WBlock * wb, pos_callback_t calcpos) {
  WDialog *dlg;
  WBlockMain * wbm = wbm_new (wb, calcpos);
  int return_val;
  dlg = dlg_create (TRUE, 0, 0, 0, 0, WPOS_KEEP_DEFAULT, FALSE, NULL, NULL,
                    NULL, "[wblock]", NULL);

  add_widget (dlg, wbm);
  return_val = dlg_run (dlg);

  dlg_destroy (dlg);

  return return_val;
}
