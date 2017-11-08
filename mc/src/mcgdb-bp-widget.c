#inc7lude <config.h>
#include <stdlib.h>
#include <stdio.h>

#include "lib/tty/tty.h"
#include "src/editor/edit-impl.h" /*LINE_STATE_WIDTH*/
#include "src/keybind-defaults.h" /*bpw_map*/

#include "src/mcgdb.h"
#include "src/mcgdb-bp.h"
#include "src/mcgdb-bp-widget.h"


typedef enum bpw_widget_type {
  BPW_BOX=1,
  BPW_BOX_END,
  BPW_CHECKBOX,
} bpw_widget_type_t;



typedef enum {
  BPW_CANCEL=0,
  BPW_OK=1
} bpw_status_t;

#define WIDGET_IDX (bpw,idx) g_array_index((bpw)->widgets_bps,bpw_widget *,idx)

typedef struct bp_widget {
  Widget w;
  GList * bps;
  GList * bps_tmp; /*copy of bps for comparsion*/
  GList * bps_del;
  GList * bps_creating;
  bpw_status_t status; /*user cancel changes*/
  gboolean redraw;
  int offset;
  int widgets_lines; /*total height of all widgets (drawed on infinite screen)*/
  GArray *widgets;
  int last_idx; /*index of last widget. after it follows widgets for creation*/
} bpw_t;


typedef struct bpw_widget {
  long x;
  long y;
  long cols;
  long lines;
  void (*draw)  (bpw_t *bpw, int idx, int y, int x);
  void (*key)   (bpw_t *bpw, int idx, int command);
  gboolean (*mouse) (bpw_t *bpw, int idx, mouse_msg_t msg, mouse_event_t * event);
  //mouse_callback;
  bpw_widget_type_t type;
  union {
    struct {
      gchar * label;
      /*box*/
    } box;
    struct {
      gchar * label;
      gboolean *flag;
      int check_y; /*position of letter 'x' in [x]*/
      int check_x;
    } checkbox;
  };
} bpw_widget_t;

static void
bpw_print_string (bpw_t *bpw, int y, int xl, int xr, const char *str, int *y1, int *x1) {
  const char *p = str;
  Widget *w = WIDGET(bpw);
  int xc=xl;
  int yc=y;
  tty_gotoyx (y, xl);
  while (*p) {
    if (xc>=w->x+w->cols) {
      yc++;
      xc=xl;
      tty_gotoyx (yc, xc);
    }
    if (yc<w->y+w->lines && yc>=w->y)
      tty_print_char (*p);
    p++;
    xc++;
  }
  *y1=yc;
  *x1=xc;
}

static gboolean
bpw_checkbox_mouse (bpw_t *bpw, int idx, mouse_msg_t msg, mouse_event_t * event) {
  bpw_widget_t *self = g_array_index (bpw->widgets,bpw_widget_t *,idx);
  switch (msg) {
    case MSG_MOUSE_CLICK:
      if (event->y==self->checkbox.check_y && event->x==self->checkbox.check_x) {
        self->checkbox.flag[0] = !self->checkbox.flag[0];
        self->draw (bpw, idx, self->y, self->x);
      }
      break;
    default:
      break;
  }
  return TRUE;
}

static void
bpw_checkbox_draw (bpw_t *bpw, int idx, int y, int x) {
  Widget *w = WIDGET (bpw);
  int x1=x,y1=y;
  int xr=w->x+w->cols;
  bpw_widget_t *self = g_array_index (bpw->widgets,bpw_widget_t *,idx);
  self->y=y;
  self->x=x;
  self->cols=WIDGET(bpw)->cols;
  if (self->checkbox.label)
    bpw_print_string (bpw, y1, x1, xr, self->checkbox.label, &y1, &x1);
  bpw_print_string (bpw, y1, x1, xr,
    self->checkbox.flag[0] ? "[x]" : "[ ]",
    &y1, &x1);
  self->checkbox.check_x = x1-2;
  self->checkbox.check_y = y1

  self->lines=y1-y+1;
}


static bpw_widget_t *
bpw_checkbox (gchar *label, gboolean *flag) {
  bpw_widget_t * w = g_new0 (bpw_widget_t,1);
  w->type = BPW_CHECKBOX;
  w->checkbox.flag = flag;
  w->checkbox.label = label;
  w->draw = bpw_checkbox_draw;
  w->mouse = bpw_checkbox_mouse;
  return w;
}

static void
bpw_box_draw (bpw_t *bpw, int idx, int y, int x) {
  bpw_widget_t *box_top = g_array_index (bpw->widgets,bpw_widget_t *,idx);
  box_top->y=y;
  box_top->x=x;
  box_top->lines=1;
  box_top->cols=WIDGET(bpw)->cols;
}

static bpw_widget_t *
bpw_box (gchar *label) {
  bpw_widget_t * w = g_new0 (bpw_widget_t,1);
  w->type = BPW_BOX;
  w->box.label = label;
  w->draw = bpw_box_draw;
  return w;
}


static void
bpw_box_end_draw (bpw_t *bpw, int idx, int y, int x) {
  Widget * w = WIDGET(bpw);
  const char *label;
  int y1,y2,bh;
  gboolean top_draw, bottom_draw;
  bpw_widget_t *box_top = NULL;
  bpw_widget_t *box_bottom = g_array_index (bpw->widgets,bpw_widget_t *,idx);

  for (int i=idx-1;i>=0;i--) {
    bpw_widget_t *tmp = g_array_index (bpw->widgets,bpw_widget_t *,i);
    if (tmp->type==BPW_BOX) {
      box_top = tmp;
      break;
    }
  }
  message_assert (box_top!=NULL);

  box_bottom->y=y;
  box_bottom->x=box_top->x;
  box_bottom->lines=1;
  box_bottom->cols=w->cols;


  label = box_top->box.label;
  top_draw = box_top->y >= w->y && box_top->y < w->y + w->lines;
  bottom_draw = box_bottom->y >= w->y && box_bottom->y < w->y + w->lines;
  if (top_draw) {
    /*draw top of box*/
    tty_gotoyx (box_top->y, box_top->x);
    tty_print_alt_char (ACS_ULCORNER, TRUE);
    tty_gotoyx (box_top->y, box_top->x+w->cols-1);
    tty_print_alt_char (ACS_URCORNER, TRUE);
    tty_draw_hline (box_top->y, box_top->x+1, mc_tty_frm[MC_TTY_FRM_HORIZ], w->cols-2);
    tty_gotoyx (box_top->y, box_top->x+w->cols/2-strlen(label)/2);
    tty_print_string (label);
  }
  if (bottom_draw) {
    /*draw bottom of box*/
    tty_gotoyx (box_bottom->y, box_top->x);
    tty_print_alt_char (ACS_LLCORNER, TRUE);
    tty_gotoyx (box_bottom->y, box_top->x+w->cols-1);
    tty_print_alt_char (ACS_LRCORNER, TRUE);
    tty_draw_hline (box_bottom->y, box_top->x+1, mc_tty_frm[MC_TTY_FRM_HORIZ], w->cols-2);
  }
  y1 = MIN(MAX(box_top->y,w->y),w->y+w->lines);
  y2 = MIN(MAX(box_bottom->y,w->y),w->y+w->lines);
  bh = y2-y1-1;
  if (bh > 0) {
    tty_draw_hline (y1+1, box_bottom->x, mc_tty_frm[MC_TTY_FRM_VERT], bh);
    tty_draw_hline (y1+1, box_bottom->x+w->cols-1, mc_tty_frm[MC_TTY_FRM_VERT], bh);
  }
}


static bpw_widget_t *
bpw_box_end (void) {
  bpw_widget_t * w = g_new0 (bpw_widget_t, 1);
  w->draw = bpw_box_end_draw;
  w->type = BPW_BOX_END;
  return w;
}



static void bpw_add_bp (bpw_t *bpw, mcgdb_bp *bp);
static bpw_t *bpw_new (void);
static void bpw_destroy (bpw_t *bpw);
static void bpw_draw (bpw_t *bpw);
static void bpw_apply_changes (bpw_t *bpw);

cb_ret_t
bpw_dialog_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  return dlg_default_callback (w, sender, msg, parm, data);
}


static cb_ret_t
bpw_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);

static void
bpw_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event);

static void
bpw_normalize_offset(bpw_t *bpw) {
  bpw->offset = MIN(MAX(bpw->offset,0),MAX(bpw->widgets_lines - WIDGET(bpw)->lines,0));
}

static gboolean
bpw_process_key (bpw_t *bpw, long command) {
  Widget *w = WIDGET(bpw);
  int handled=MSG_NOT_HANDLED;
  gboolean redraw = FALSE;
  switch (command) {
    case CK_Up:
      bpw->offset-=1;
      handled=MSG_HANDLED;
      redraw=TRUE;
      break;
    case CK_Down:
      bpw->offset+=1;
      handled=MSG_HANDLED;
      redraw=TRUE;
      break;
    case CK_PageUp:
      bpw->offset-=w->lines/3;
      handled=MSG_HANDLED;
      redraw=TRUE;
      break;
    case CK_PageDown:
      bpw->offset+=w->lines/3;
      handled=MSG_HANDLED;
      redraw=TRUE;
      break;
    default:
      break;
  }
  bpw_normalize_offset (bpw);
  if (redraw)
    bpw_draw (bpw);
  return handled;
}

static cb_ret_t
bpw_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  long command;
  bpw_t *bpw = (bpw_t *)w;


  switch (msg) {
    case MSG_RESIZE:
      bpw_normalize_offset (bpw);
      return MSG_HANDLED;
    case MSG_INIT:
    case MSG_DRAW:
      bpw_draw (bpw);
      return MSG_HANDLED;
    case MSG_KEY:
      command = keybind_lookup_keymap_command (mcgdb_bpw_map, parm);
      if (bpw->current_widget_idx!=-1) {
        int idx=bpw->current_widget_idx;
        if (WIDGET_IDX (bpw,idx)->key (bpw,idx,command) == MSG_HANDLED)
          return MSG_HANDLED;
      }
      return bpw_process_key (bpw, command);
    case MSG_DESTROY:
      bpw_destroy (bpw);
      return MSG_HANDLED;
    default:
      return MSG_NOT_HANDLED;
  }
}

static int
bpw_widget_yx_idx (bpw_t *bpw, int y, int x) {
  for (int idx=0;idx<bpw->widgets; idx++) {
    bpw_widget_t *bw = WIDGET_IDX (bpw,idx);
    if (bw->y<=y && y<bw->y+bw->lines && bw->x<=x && x<bw->x+bw->lines) {
      return idx;
    }
  }
  return -1;
}

static void
bpw_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
  bpw_t *bpw = (bpw_t *)w;

  int idx = bpw_widget_yx_idx (bpw,event->y,event->x);
  if (idx>=0) {
    if (WIDGET_IDX (bpw,idx)->mouse (bpw,idx,msg,event))
      return;
  }

  switch (msg) {
    case MSG_MOUSE_SCROLL_UP:
      bpw->offset-=2;
      bpw_normalize_offset (bpw);
      break;
    case MSG_MOUSE_SCROLL_DOWN:
      bpw->offset+=2;
      bpw_normalize_offset (bpw);
      break;
    default:
      break;
  }

}


static bpw_t *
bpw_new (void) {
  bpw_t * bpw = g_new0 (bpw_t, 1);
  bpw->widgets    = g_array_new (FALSE,FALSE,sizeof(bpw_widget_t *));
  widget_init (WIDGET(bpw), 1, 1, 1, 1, bpw_callback, bpw_mouse_callback);
  widget_set_options (WIDGET(bpw), WOP_SELECTABLE, TRUE);
  return bpw;
}

static void
bpw_destroy (bpw_t *bpw) {
  g_list_free (bpw->bps);
  g_list_free_full (bpw->bps_tmp, (GDestroyNotify) mcgdb_bp_free);
  g_list_free_full (bpw->bps_creating, (GDestroyNotify) mcgdb_bp_free);
}

static void
bpw_draw (bpw_t *bpw) {
  Widget *w = WIDGET(bpw);
  int lines = MAX(3,LINES-8);
  int cols = 40;
  int x=LINE_STATE_WIDTH+2;
  int y=4;
  int draw_x, draw_y;
  tty_fill_region (y, x, lines, cols, ' ');
  w->y=y;
  w->x=x;
  w->lines=lines;
  w->cols=cols;
  draw_x = w->x;
  draw_y = w->y - bpw->offset;
  bpw->widgets_lines = draw_y;
  for (size_t i=0;i<bpw->widgets->len;i++) {
    bpw_widget_t *bw = g_array_index (bpw->widgets,bpw_widget_t *,i);
    bw->draw (bpw,i,draw_y,draw_x);
    draw_y = bw->y+bw->lines;
    if (bw->type==BPW_BOX)
      draw_x+=2;
    else if (bw->type==BPW_BOX_END)
      draw_x-=2;
  }
  bpw->widgets_lines = draw_y - bpw->widgets_lines;
}

static void
bpw_apply_changes (bpw_t *bpw) {
  GList *l,*ltmp;
  for (l=bpw->bps,ltmp=bpw->bps_tmp; l; l=l->next,ltmp=ltmp->next) {
    mcgdb_bp *bp = MCGDB_BP (l), *bp_tmp = MCGDB_BP (ltmp);
    if (!mcgdb_bp_equals (bp, bp_tmp)) {
      send_pkg_update_bp (bp);
      mcgdb_bp_assign (bp, bp_tmp);
      bpw->redraw=TRUE;
    }
  }

  for (l=bpw->bps_del; l; l=l->next) {
    mcgdb_bp *bp = MCGDB_BP (l);
    send_pkg_delete_bp (bp);
    bpw->redraw=TRUE;
  }

  for (l=bpw->bps_creating; l; l=l->next) {
    mcgdb_bp *bp = MCGDB_BP (l);
    send_pkg_update_bp (bp);
    bpw->redraw=TRUE;
    insert_bp_to_list (bp);
  }


}

static void
bpw_add_bp (bpw_t *bpw, mcgdb_bp *bp) {
  mcgdb_bp *tmp_bp;
  bpw->bps = g_list_append (bpw->bps, bp);
  tmp_bp = mcgdb_bp_copy (bp);
  bpw->bps_tmp = g_list_append (bpw->bps_tmp, tmp_bp);
  {
    int len=0;
    bpw_widget_t * widgets[] = {
      bpw_box (g_strdup_printf ("Breakpoint %d",tmp_bp->number)),
        bpw_checkbox (strdup("enabled: "),&tmp_bp->enabled),
      bpw_box_end (),
      NULL
    };
    while (widgets[len]) {len++;}
    g_array_append_vals (bpw->widgets, widgets, len);
  }
}

gboolean
is_bpw_dialog (WDialog *h) {
  return h->widget.callback==bpw_dialog_callback;
}

gboolean
breakpoints_edit_dialog (const char *filename, long line) {
  WDialog *dlg;
  bpw_t *bpw;
  gboolean redraw;
  dlg = dlg_create (TRUE, 0, 0, 0, 0, WPOS_KEEP_DEFAULT, FALSE, NULL, bpw_dialog_callback,
                    NULL, "[breakpoints]", NULL);
  bpw = bpw_new ();

  for ( GList *l=mcgdb_bp_find_bp_with_location (mcgdb_bps, filename, line);
        l!=0;
        l = mcgdb_bp_find_bp_with_location (l->next, filename, line))
  {
    bpw_add_bp (bpw, MCGDB_BP (l));
  }

  add_widget (dlg, bpw);
  disable_gdb_events = TRUE;
  dlg_run (dlg);
  disable_gdb_events = FALSE;

  if (bpw->status==BPW_OK)
    bpw_apply_changes (bpw);

  redraw = bpw->redraw;

  dlg_destroy (dlg);

  return redraw;
}
