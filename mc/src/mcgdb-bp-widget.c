#include <config.h>
#include <stdlib.h>
#include <stdio.h>

#include "lib/tty/tty.h"
#include "src/editor/edit-impl.h" /*LINE_STATE_WIDTH*/
#include "src/keybind-defaults.h" /*bpw_map*/

#include "src/mcgdb.h"
#include "src/mcgdb-bp.h"
#include "src/mcgdb-bp-widget.h"

typedef enum {
  BPW_CANCEL=0,
  BPW_OK=1
} bpw_status_t;

typedef struct bp_widget {
  Widget w;
  GList * bps;
  GList * bps_tmp; /*copy of bps for comparsion*/
  GList * bps_del;
  GList * bps_creating;
  bpw_status_t status; /*user cancel changes*/
  gboolean redraw;
  int offset;
} bpw_t;


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

static gboolean
bpw_process_key (bpw_t *bpw, long command) {
  Widget *w = WIDGET(bpw);
  switch (command) {
    case CK_Up:
      bpw->offset-=1;
      return MSG_HANDLED;
    case CK_Down:
      bpw->offset+=1;
      return MSG_HANDLED;
    case CK_PageUp:
      bpw->offset-=w->lines/3;
      return MSG_HANDLED;
    case CK_PageDown:
      bpw->offset+=w->lines/3;
      return MSG_HANDLED;
    default:
      return MSG_NOT_HANDLED;
  }
}

static cb_ret_t
bpw_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  long command;
  bpw_t *bpw = (bpw_t *)w;
  switch (msg) {
    case MSG_INIT:
    case MSG_DRAW:
    case MSG_RESIZE:
      bpw_draw (bpw);
      return MSG_HANDLED;
    case MSG_KEY:
      command = keybind_lookup_keymap_command (mcgdb_bpw_map, parm);
      return bpw_process_key (bpw, command);
    case MSG_DESTROY:
      bpw_destroy (bpw);
      return MSG_HANDLED;
    default:
      return MSG_NOT_HANDLED;
  }
}

static void
bpw_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {

}


static bpw_t *
bpw_new (void) {
  bpw_t * bpw = g_new0 (bpw_t, 1);
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
  tty_fill_region (y, x, lines, cols, ' ');
  w->y=y;
  w->x=x;
  w->lines=lines;
  w->cols=cols;
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
  }


}

static void
bpw_add_bp (bpw_t *bpw, mcgdb_bp *bp) {
  bpw->bps = g_list_append (bpw->bps, bp);
  bpw->bps_tmp = g_list_append (bpw->bps_tmp, mcgdb_bp_copy (bp));
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
