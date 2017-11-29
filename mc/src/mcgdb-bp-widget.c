#include <config.h>
#include "lib/widget/wblock.h"
#include "mcgdb-bp-widget.h"
#include "mcgdb.h"
#include "mcgdb-bp.h"
#include "lib/tty/tty.h"        /* LINES */

typedef struct bp_pair {
  mcgdb_bp *orig;
  mcgdb_bp *temp;
} bp_pair_t;

typedef struct BPWidget {
  WBlock wb;
  GList * bps; /*bp_pair*/
  gboolean redraw;
} BPWidget;

static void calcpos (int *y, int *x, int *lines, int *cols);
static BPWidget * bpw_new (void);
static void bpw_free (BPWidget *bpw);
static bp_pair_t * bpw_add_bp (BPWidget *bpw, mcgdb_bp *bp);
static void bpw_apply_changes (BPWidget *bpw);

static void
calcpos (int *y, int *x, int *lines, int *cols) {
  *y=5;
  *x=9;
  *lines=MAX (3,MIN (20,LINES-7));
  *cols=40;
}

static BPWidget *
bpw_new (void) {
  BPWidget *bpw = g_new0 (BPWidget,1);
  wblock_init (&bpw->wb,NULL,NULL,NULL,NULL,NULL,NULL);
  return bpw;
}

static void
bpw_free (BPWidget *bpw) {
  WBLOCK_DESTROY (&bpw->wb);
  g_free (bpw);
}


static void
bpw_delete_all (WBlock *wb, gpointer data) {
  GList *pairs = (GList *)data;
  for (GList *l=pairs;l;l=l->next) {
    ((bp_pair_t *)(l->data))->temp->wait_status = BP_WAIT_DELETE;
  }
  wblock_button_ok (wb, data);
}

static WBlock *
buttons_widget (BPWidget *bpw) {
  WBlock *top = wblock_empty ();

  wblock_add_widget (top, layout_inline (wblock_button_new (
    strdup ("[DeleteAll]"),
    bpw_delete_all,
    bpw->bps,
    NULL
  )));

  wblock_add_widget (top, wblock_nspace (1));

  wblock_add_widget (top, layout_inline (wblock_button_new (
    strdup ("[Save]"),
    wblock_button_ok,
    NULL,
    NULL
  )));

  wblock_add_widget (top, wblock_nspace (1));

  wblock_add_widget (top, layout_inline (wblock_button_new (
    strdup ("[Cancel]"),
    wblock_button_cancel,
    NULL,
    NULL
  )));

  top->style.align = ALIGN_CENTER;
  return top;
}

static WBlock *
bpw_epilog (BPWidget *bpw) {
  WBlock *buttons = buttons_widget (bpw);
  return buttons;
}

static WBlock *
bpw_prolog (BPWidget *bpw) {
  WBlock *buttons = buttons_widget (bpw);
  return buttons;
}



static char *
last_slash (int n, const char *str) {
  /* a/b/c.txt
    n==0 => c.txt
    n==1 => b/c.txt
  */
  const char *last, *p=str;
  while (*p)
    last=p++;
  for (;last!=str;last--) {
    if (*last=='/') {
      if (n<=0)
        return strdup (last+1);
      else
        n--;
    }
  }

  return strdup (str);
}

typedef struct {
  BPWidget *bpw;
  bp_pair_t *bp_pair;
  WBlock *parent;
} ButtonDeleteData;

static void
bpw_button_delete_cb (WBlock *wb, gpointer gdata) {
  WBlock *frame_parent;
  ButtonDeleteData *data = (ButtonDeleteData *)gdata;
  mcgdb_bp *orig = data->bp_pair->orig,
           *temp = data->bp_pair->temp;
  WBlockFrameData *frame_data;
  int new_frame_color;
  if (orig!=NULL) {
    if (temp->wait_status!=BP_WAIT_DELETE) {
      temp->wait_status = BP_WAIT_DELETE;
    }
    else {
      if (orig->wait_status==BP_WAIT_UPDATE || !mcgdb_bp_equals (orig, temp)) {
        temp->wait_status = BP_WAIT_UPDATE;
      }
      else {
        temp->wait_status = orig->wait_status;
      }
    }
    frame_parent = data->parent; /*frame around breakpoint widget*/
    message_assert (frame_parent!=NULL);
    frame_data = WBLOCK_FRAME_DATA (frame_parent->wdata);
    switch (temp->wait_status) {
      case BP_WAIT_DELETE:
        new_frame_color = COLOR_BP_FRAME_WAIT_DELETE;
        break;
      case BP_WAIT_UPDATE:
        new_frame_color = WBLOCK_FRAME_COLOR_NORMAL;
        break;
      default:
        new_frame_color = WBLOCK_FRAME_COLOR_NORMAL;
        break;
    }
    if (frame_data->color != new_frame_color) {
      frame_data->color = new_frame_color;
      wb->parent->redraw = TRUE;
    }
  }
  else {
    if (wb->parent) {
      wb->parent->widgets = g_list_remove (wb->parent->widgets, wb);
      wb->parent->redraw = TRUE;
    }
    WBLOCK_DESTROY(wb);
  }
}

static bp_pair_t *
bpw_add_bp (BPWidget *bpw, mcgdb_bp *bp) {
  bp_pair_t *bp_pair = g_new0 (bp_pair_t, 1);
  mcgdb_bp *bp_tmp = mcgdb_bp_copy (bp);
  bp_pair->orig = bp;
  bp_pair->temp = bp_tmp;
  bpw->bps = g_list_append (bpw->bps, bp_pair);
  return bp_pair;
}

static WBlock *
bp_widget (BPWidget *bpw, bp_pair_t *bp_pair) {
  int location_idx=1;
  mcgdb_bp *bp_tmp = bp_pair->temp;
  WBlock *widget_bp, *top_widget;
  WBlock *widget_locs = wblock_new (NULL,NULL,NULL,NULL,NULL,NULL);
  top_widget = wblock_new (NULL,NULL,NULL,NULL,NULL,NULL);
  widget_bp = wblock_frame_new (g_strdup_printf ("Breakpoint %d",bp_tmp->number));
  widget_bp->style.layout=LAYOUT_INLINE;
  wblock_add_widget (top_widget, widget_bp);

  {
    ButtonDeleteData *data = g_new0 (ButtonDeleteData,1);
    WBlock *delbtn;
    data->bpw=bpw;
    data->bp_pair = bp_pair;
    data->parent = widget_bp;
    delbtn = wblock_button_new (
          strdup ("[DEL]"),
          bpw_button_delete_cb,
          (gpointer) data,
          NULL);
    delbtn->style.margin.left=-6;
    delbtn->style.layout=LAYOUT_INLINE;
    wblock_add_widget (top_widget, delbtn);
  }


  wblock_add_widget (widget_bp,wblock_label_new (strdup("Locations:"),TRUE));
  widget_locs->style.margin.left=2;

  for (GList *l=bp_tmp->locations;l;l=l->next, location_idx++) {
    char *short_fname = last_slash (1, BP_LOC (l)->filename); /*keep one or 0 slashes*/
    wblock_add_widget (
      widget_locs,
      wblock_multilabel_new (
        FALSE,
        g_strdup_printf ("%d. %s:%d",location_idx, short_fname, BP_LOC (l)->line),
        g_strdup_printf ("%d. %s:%d",location_idx, BP_LOC (l)->filename, BP_LOC (l)->line),
        NULL
    ));
    g_free (short_fname);
  }

  wblock_add_widget (widget_bp, widget_locs);

  wblock_add_widget (
    widget_bp,
    wblock_checkbox_labeled_new (
      strdup ("enabled "),
      &bp_tmp->enabled
  ));

  wblock_add_widget (
    widget_bp,
    wblock_checkbox_labeled_new (
      strdup ("silent  "),
      &bp_tmp->silent
  ));

  wblock_add_widget (
    widget_bp,
    wblock_input_new (
      &bp_tmp->condition, 1, 5
  ));


  return top_widget;
}


static void
bpw_apply_changes (BPWidget *bpw) {
  for (GList *l=bpw->bps;l;l=l->next) {
    bp_pair_t *p = (bp_pair_t *)(l->data);
      mcgdb_bp  *orig = p->orig,
                *temp = p->temp;

    if (orig && temp) {
      if (orig->wait_status!=BP_WAIT_DELETE && temp->wait_status!=BP_WAIT_DELETE) {
        /*compare*/
        if (!mcgdb_bp_equals (orig, temp)) {
          /*update*/
          temp->wait_status=BP_WAIT_UPDATE;
          send_pkg_update_bp (temp);
          mcgdb_bp_assign (orig,temp);
          bpw->redraw=TRUE;
        }
      }
      else if (orig->wait_status==BP_WAIT_DELETE && temp->wait_status!=BP_WAIT_DELETE) {
        /*update*/
        temp->wait_status=BP_WAIT_UPDATE;
        send_pkg_update_bp (temp);
        mcgdb_bp_assign (orig,temp);
        bpw->redraw=TRUE;
      }
      else if (orig->wait_status!=BP_WAIT_DELETE && temp->wait_status==BP_WAIT_DELETE) {
        /*delete*/
        temp->wait_status=BP_WAIT_DELETE;
        send_pkg_delete_bp (temp);
        mcgdb_bp_assign (orig,temp);
        bpw->redraw=TRUE;
      }
      else if (orig->wait_status==BP_WAIT_DELETE && temp->wait_status==BP_WAIT_DELETE) {
        /*do nothing*/
      }

    }
    else if (orig==NULL && temp!=NULL) {
      /*creation*/
      temp->wait_status=BP_WAIT_UPDATE;
      send_pkg_update_bp (temp);
      bpw->redraw=TRUE;
      insert_bp_to_list (temp);
    }
    else {
      message_assert (FALSE);
    }
  }
}


gboolean
breakpoints_edit_dialog (const char *filename, long line) {
  BPWidget *bpw = bpw_new ();
  WBlock    *widget_bps = wblock_empty ();
  gboolean redraw;
  int return_val;

  for ( GList *l=mcgdb_bp_find_bp_with_location (mcgdb_bps, filename, line);
        l!=0;
        l = mcgdb_bp_find_bp_with_location (l->next, filename, line))
  {
    mcgdb_bp *bp = MCGDB_BP (l);
    bp_pair_t *bp_pair = bpw_add_bp (bpw, bp);
    wblock_add_widget (widget_bps, bp_widget (bpw, bp_pair));
  }

  wblock_add_widget (WBLOCK (bpw), wblock_newline ());
  wblock_add_widget (WBLOCK (bpw), bpw_prolog (bpw));
  wblock_add_widget (WBLOCK (bpw), wblock_newline ());
  wblock_add_widget (WBLOCK (bpw), widget_bps);
  wblock_add_widget (WBLOCK (bpw), bpw_epilog (bpw));
  wblock_add_widget (WBLOCK (bpw), wblock_newline ());

  disable_gdb_events = TRUE;
  return_val = wblock_run (WBLOCK (bpw), calcpos);
  disable_gdb_events = FALSE;

  if (return_val!=B_CANCEL)
    bpw_apply_changes (bpw);

  redraw = bpw->redraw;
  bpw_free (bpw);

  return redraw;
}
