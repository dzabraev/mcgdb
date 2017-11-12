#include <config.h>
#include "lib/widget/wblock.h"
#include "mcgdb-bp-widget.h"
#include "mcgdb.h"
#include "mcgdb-bp.h"

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
  *lines=20;
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

static void
bpw_add_bp (BPWidget *bpw, mcgdb_bp *bp) {
  WBlock *widget_bp;
  mcgdb_bp *tmp_bp;
  bpw->bps = g_list_append (bpw->bps, bp);
  tmp_bp = mcgdb_bp_copy (bp);
  bpw->bps_tmp = g_list_append (bpw->bps_tmp, tmp_bp);
  widget_bp = wb_frame_new (g_strdup_printf ("Breakpoint %d",tmp_bp->number));
  
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
