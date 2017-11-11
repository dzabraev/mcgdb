#include <config.h>
#include <strings.h>

#include "lib/widget/block-widget.h"


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
  do_draw)


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
  gboolean res;
  event->y-=w->y;
  event->x-=w->x;
  res = WBLOCK_MOUSE (wbm->wb, msg, event);
  event->y+=w->y;
  event->x+=w->x;
  if (res)
	return

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
	WBM_WBLOCK_DRAW (wbm,TRUE);
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
  	  {
  		int y,x,lines,cols;
        WBMAIN(w)->calcpos(&y,&x,&lines,&cols);
        w->x=x;
        w->y=y;
        w->lines=lines;
        w->cols=cols;
      }
      WBM_WBLOCK_DRAW (wbm,FALSE);
      break;
    case MSG_DRAW:
      WBM_WBLOCK_DRAW (wbm,TRUE);
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
    	WBM_WBLOCK_DRAW (wbm,TRUE);
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
  if (!YX_IN_WIDGET (wb,y,x))
	return NULL;

  for (GList *l=g_list_last (wb->widgets);l;l=l->prev) {
	WBlock *c = WBLOCK (l);
	if (YX_IN_WIDGET (c,y,x)) {
	  return wblock_get_widget_yx (c, y, x);
	}
  }

  return wb;
}

gboolead
wblock_dfl_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event) {
  WBlock *c = wblock_get_widget_yx (wb, event->y, event->x); //most depth widget
  while (c) {
	if (c->mouse) {
	  gboolean res;
	  event->x-=c->x;
	  event->y-=c->y;
	  res = WBLOCK_MOUSE (c, msg, event);
	  event->x+=c->x;
	  event->y+=c->y;
	  if (res)
		return TRUE
	}
	c = c->parent;	
  }
  wb->selected_widget = NULL;
  return FALSE;
}

void
wblock_dfl_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  int y_line=y0,
      y_line_bottom=y0,
      x_line=x0;
 
  for (GList *l=wb->widgets;l;l=l->next) {
    int y_widget, x_widget;
    WBlock *c = WBLOCK (l);

    if (c->style.layout==LAYOUT_BLOCK) {
	  y_widget = y_line_bottom;
	  x_widget = x0;
    }
    else if (c->style.layout==LAYOUT_INLINE) {
	  y_widget = y_line;
	  x_widget = x_line;
    }

    x_widget+=c->style.margin.left;
    y_widget+=c->style.margin.top;

	c->y = y_widget;
	c->x = x_widget;
	c->lines=-1;
	c->cols=-1;
    WBLOCK_DRAW (c, y_widget, x_widget, y, x, lines, cols, do_draw);
    message_assert (c->lines>=0);
    message_assert (c->cols>=0);
    

	y_line_bottom = MAX(y_line_bottom, y_widget+c->lines+c->style.margin.bottom);

    if (c->style.layout==LAYOUT_BLOCK) {
	  y_widget = y_line_bottom;
	  x_widget = x0;
    }
    else if (c->style.layout==LAYOUT_INLINE) {
	  x_line+=c->lines+x->style.margin.right;
    }
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
  g_free (wb->data);
}

WBlock *
wblock_init (
  WBlock *wb
  wblock_mouse_cb_t   mouse,
  wblock_key_cb_t     key,
  wblock_destroy_cb_t destroy,
  wblock_draw_cb_t    draw,
  gpointer wdata)
{
  bzero (wb, sizeof (WBlock));
  wb->destroy   = destroy   ? destroy   : wblock_dfl_default;
  wb->draw      = draw      ? draw      : wblock_dfl_draw;
  wb->key       = key       ? key       : wblock_dfl_key;
  wb->mouse     = mouse     ? mouse     : wblock_dfl_mouse;
  wv->wdata     = wdata;
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
  wblock_init (wb, mouse, key, destroy, wdata);
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
