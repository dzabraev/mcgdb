#include <config.h>
#include "lib/widget/wblock.h"
#include "mcgdb-bp-widget.h"
#include "mcgdb.h"
#include "mcgdb-bp.h"
#include "lib/tty/tty.h"        /* LINES */

typedef struct BPWidget {
  WBlock wb;
  GList * bps;
  GList * bps_tmp; /*copy of bps for comparsion*/
  GList * bps_del;
  GList * bps_creating;
  gboolean redraw;
} BPWidget;

static void calcpos (int *y, int *x, int *lines, int *cols);
static BPWidget * bpw_new (void);
static void bpw_free (BPWidget *bpw);
static void bpw_add_epilogue (BPWidget *bpw);
static void bpw_add_bp (BPWidget *bpw, mcgdb_bp *bp);
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
  wblock_init (&bpw->wb,NULL,NULL,NULL,NULL,NULL);
  return bpw;
}

static void
bpw_free (BPWidget *bpw) {
  WBLOCK_DESTROY (&bpw->wb);
  g_free (bpw);
}

static void
bpw_add_epilogue (BPWidget *bpw) {

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

struct {
  BPWidget *bpw;
  int * color;
  gboolean direct_delete;
} ButtonDeleteData;

static void
bpw_button_delete_cb (WBlock *wb, gointer data) {

}

static void
bpw_add_bp (BPWidget *bpw, mcgdb_bp *bp) {
  int location_idx=1;
  WBlock *widget_bp;
  WBlock *widget_locs = wblock_new (NULL,NULL,NULL,NULL,NULL);
  mcgdb_bp *tmp_bp;
  bpw->bps = g_list_append (bpw->bps, bp);
  tmp_bp = mcgdb_bp_copy (bp);
  bpw->bps_tmp = g_list_append (bpw->bps_tmp, tmp_bp);
  widget_bp = wblock_frame_new (g_strdup_printf ("Breakpoint %d",tmp_bp->number));

  wblock_add_widget (
    widget_bp,
    wblock_button_new (
        strdup ("[Delete Breakpoint]"),
        bpw_button_delete_cb,
        (gpointer) bpw_button_delete_data)
  );


  wblock_add_widget (widget_bp,wblock_label_new (strdup("Locations:"),TRUE));
  widget_locs->style.margin.left=2;

  for (GList *l=tmp_bp->locations;l;l=l->next, location_idx++) {
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
      &tmp_bp->enabled
  ));

  wblock_add_widget (
    widget_bp,
    wblock_checkbox_labeled_new (
      strdup ("silent  "),
      &tmp_bp->silent
  ));

  wblock_add_widget (WBLOCK (bpw), widget_bp);
}


static void
bpw_apply_changes (BPWidget *bpw) {
  GList *l,*ltmp;
  for (l=bpw->bps,ltmp=bpw->bps_tmp; l; l=l->next,ltmp=ltmp->next) {
    mcgdb_bp *bp = MCGDB_BP (l), *bp_tmp = MCGDB_BP (ltmp);
    if (!mcgdb_bp_equals (bp, bp_tmp) && !g_list_find (bpw->bps_del,bp_tmp)) {
      mcgdb_bp_assign (bp, bp_tmp);
      bp->wait_status=BP_WAIT_UPDATE;
      send_pkg_update_bp (bp);
      bpw->redraw=TRUE;
    }
  }

  for (l=bpw->bps_del; l; l=l->next) {
    mcgdb_bp *bp = MCGDB_BP (l);
    bp->wait_status=BP_WAIT_DELETE;
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


gboolean
breakpoints_edit_dialog (const char *filename, long line) {
  BPWidget *bpw = bpw_new ();
  gboolean redraw;
  int return_val;
  

  for ( GList *l=mcgdb_bp_find_bp_with_location (mcgdb_bps, filename, line);
        l!=0;
        l = mcgdb_bp_find_bp_with_location (l->next, filename, line))
  {
    bpw_add_bp (bpw, MCGDB_BP (l));
  }

  bpw_add_epilogue (bpw); /*save/cancel buttons, widgets for creation*/

  disable_gdb_events = TRUE;
  return_val = wblock_run (WBLOCK (bpw), calcpos);
  disable_gdb_events = FALSE;

  if (return_val!=B_CANCEL)
    bpw_apply_changes (bpw);

  redraw = bpw->redraw;
  bpw_free (bpw);
  
  return redraw;
}
