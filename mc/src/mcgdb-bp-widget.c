#include <config.h>
#include "lib/widget/wblock.h"
#include "mcgdb-bp-widget.h"
#include "mcgdb.h"
#include "mcgdb-bp.h"
#include "lib/tty/tty.h"          /* LINES, COLS */
#include "src/editor/edit-impl.h" /* LINE_STATE_WIDTH*/


typedef struct bp_pair {
  mcgdb_bp *orig;
  mcgdb_bp *temp;
} bp_pair_t;


static gboolean bpw_apply_changes (GList *pairs);
static bp_pair_t * bp_pair_new (mcgdb_bp *bp);
static void bp_pair_free (bp_pair_t *pair);



static void bpw_delete_all (WBlock *wb, gpointer data);


static void
bpw_delete_all (WBlock *wb, gpointer data) {
  GList *pairs = (GList *)data;
  for (GList *l=pairs;l;l=l->next) {
    ((bp_pair_t *)(l->data))->temp->wait_status = BP_WAIT_DELETE;
  }
  wblock_button_ok (wb, data);
}

static WBlock *
bprm_widget (GList *pairs) {
  WBlock *wb = wblock_button_new (
      strdup ("[DelAll]"),
      bpw_delete_all,
      pairs,
      NULL
  );
  return wb;
}

static WBlock *
buttons_widget (GList **pairs) {
  WBlock *top = wblock_empty ();

  (void) pairs;

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
bpw_epilog (GList **pairs) {
  WBlock *buttons = buttons_widget (pairs);
  return buttons;
}

static WBlock *
bpw_prolog (GList **pairs) {
  WBlock *buttons = buttons_widget (pairs);
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
  GList **pairs;
  bp_pair_t *pair;
  WBlock *parent;
} ButtonDeleteData;

static void
bpw_button_delete_cb (WBlock *wb, gpointer gdata) {
  WBlock *frame_parent;
  ButtonDeleteData *data = (ButtonDeleteData *)gdata;
  mcgdb_bp *orig = data->pair->orig,
           *temp = data->pair->temp;
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
    wblock_set_color (wb, new_frame_color);
  }
  else {
    bp_pair_t *pair = data->pair;
    if (wb->parent) {
      wb->parent->widgets = g_list_remove (wb->parent->widgets, wb);
      wb->parent->redraw = TRUE;
    }
    data->pairs[0] = g_list_remove (data->pairs[0],pair);
    bp_pair_free (pair);
    wblock_destroy (wb);
  }
}



static WBlock *
thread_widget_new (thread_entry_t *t) {
  WBlock *wb = wblock_empty ();
  wblock_add_widget (wb,
    layout_inline (wblock_label_new (
      g_strdup_printf ("#%d", t->global_num), FALSE
  )));
  wblock_add_widget (wb, wblock_nspace (1));
  wblock_add_widget (wb,
    layout_inline (wblock_label_new (
      g_strdup_printf ("%s pid=%d tid=%d lwp=%d", t->name, t->pid, t->tid, t->lwp), FALSE
  )));
  return wb;
}


static GList *
get_setect_options_for_threads (int initial_id, gboolean add_none) {
  GList *options = NULL;

  if (add_none) {
    WBlock *wb_none = wblock_label_new (g_strdup ("#0 No thread"), FALSE);
    options = g_list_append (options,select_option_new (-1, wb_none, -1, g_strdup ("[#0 No thread]")));
  }

  for (GList *tl=thread_list;tl;tl=tl->next) {
    gboolean selected;
    WBlock *row = wblock_empty ();
    char *short_name;
    thread_entry_t *t = (thread_entry_t *)tl->data;
    wblock_add_widget (row, thread_widget_new (t));
    selected = t->global_num==initial_id;
    short_name = g_strdup_printf ("[#%d %s]",t->global_num, t->name);
    options = g_list_append (options, select_option_new (t->global_num, row, selected, short_name));
  }
  return options;
}


static WBlock *
wblock_button_select_thread (int *global_num, gboolean add_none) {
  return wblock_button_select_new (
    global_num,
    get_setect_options_for_threads 
      (global_num[0], add_none));
}


static WBlock *
bp_widget (GList **pairs, bp_pair_t *pair) {
  int location_idx=1;
  mcgdb_bp *bp_tmp = pair->temp;
  WBlock  *widget_bp,
          *top_widget = wblock_empty ();
  WBlock *widget_locs = wblock_empty ();
  WBlock *widget_ign_count = wblock_empty ();

  widget_bp = wblock_frame_new (g_strdup_printf ("Breakpoint %d",bp_tmp->number));
  widget_bp->style.layout=LAYOUT_INLINE;
  wblock_add_widget (top_widget, widget_bp);

  {
    ButtonDeleteData *data = g_new0 (ButtonDeleteData,1);
    WBlock *delbtn;
    data->pairs=pairs;
    data->pair = pair;
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



  wblock_add_widget (
    widget_bp,
    wblock_label_new (
      g_strdup_printf ("Hit count: %d", bp_tmp->hit_count), TRUE
    )
  );


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

  wblock_add_widget (widget_bp, wblock_newline ());


  wblock_add_widget (
    widget_ign_count,
    layout_inline (wblock_label_new (
      g_strdup ("Ignore count "), TRUE
    ))
  );

  wblock_add_widget (
    widget_ign_count,
    layout_inline (wblock_input_integer_new (
      &bp_tmp->ignore_count
    ))
  );

  wblock_add_widget (widget_bp, widget_ign_count);


  wblock_add_widget (
    widget_bp,
    wblock_checkbox_labeled_new (
      strdup ("Enabled "),
      &bp_tmp->enabled
  ));

  wblock_add_widget (
    widget_bp,
    wblock_checkbox_labeled_new (
      strdup ("Silent  "),
      &bp_tmp->silent
  ));


  {
    WBlock *wb_th = wblock_empty ();
    wblock_add_widget (
      wb_th,
      layout_inline (wblock_label_new (
        g_strdup ("Thread  "), TRUE
      ))
    );
    wblock_add_widget (
      wb_th,
      layout_inline (wblock_button_select_thread (&bp_tmp->thread, TRUE))
    );
    wblock_add_widget (widget_bp, wb_th);
  }

  wblock_add_widget (widget_bp, wblock_newline ());

  wblock_add_widget (
    widget_bp,
    wblock_label_new (
      g_strdup ("Condition"), TRUE
    )
  );

  wblock_add_widget (
    widget_bp,
    wblock_input_new (
      &bp_tmp->condition, 2, 5, -1, -1
  ));

  wblock_add_widget (widget_bp, wblock_newline ());

  wblock_add_widget (
    widget_bp,
    wblock_label_new (
      g_strdup ("Commands (read-only)"), TRUE
    )
  );

  {
    WBlock *wb = wblock_input_new (
      &bp_tmp->commands, 2, 5, -1, -1
    );
    wblock_input_set_readonly (wb, TRUE);
    wblock_add_widget (widget_bp,wb);
  }


  return top_widget;
}


static gboolean
bpw_apply_changes (GList *pairs) {
  gboolean redraw = FALSE; /*will we need redraw editor linenum columns?*/
  for (GList *l=pairs;l;l=l->next) {
    bp_pair_t *pair = (bp_pair_t *)(l->data);
      mcgdb_bp  *orig = pair->orig,
                *temp = pair->temp;

    if (orig && temp) {
      if (orig->wait_status!=BP_WAIT_DELETE && temp->wait_status!=BP_WAIT_DELETE) {
        /*compare*/
        if (!mcgdb_bp_equals (orig, temp)) {
          /*update*/
          temp->wait_status=BP_WAIT_UPDATE;
          send_pkg_update_bp (temp);
          mcgdb_bp_assign (orig,temp);
          redraw=TRUE;
        }
      }
      else if (orig->wait_status==BP_WAIT_DELETE && temp->wait_status!=BP_WAIT_DELETE) {
        /*update*/
        temp->wait_status=BP_WAIT_UPDATE;
        send_pkg_update_bp (temp);
        mcgdb_bp_assign (orig,temp);
        redraw=TRUE;
      }
      else if (orig->wait_status!=BP_WAIT_DELETE && temp->wait_status==BP_WAIT_DELETE) {
        /*delete*/
        temp->wait_status=BP_WAIT_DELETE;
        send_pkg_delete_bp (temp);
        mcgdb_bp_assign (orig,temp);
        redraw=TRUE;
      }
      else if (orig->wait_status==BP_WAIT_DELETE && temp->wait_status==BP_WAIT_DELETE) {
        /*do nothing*/
      }
    }
    else if (orig==NULL && temp!=NULL) {
      /*creation*/
      if (temp->wait_status==BP_WAIT_DELETE) {
        continue;
      }
      temp->wait_status=BP_WAIT_UPDATE;
      send_pkg_update_bp (temp);
      redraw=TRUE;
      insert_bp_to_list (temp);
      pair->orig = pair->temp;
      pair->temp = NULL;
    }
    else {
      message_assert (FALSE);
    }
  }
  return redraw;
}

static bp_pair_t *
bp_pair_new (mcgdb_bp *bp) {
  bp_pair_t *pair = g_new0 (bp_pair_t, 1);
  pair->orig = bp;
  pair->temp = mcgdb_bp_copy (bp);
  return pair;
}

static void
bp_pair_free (bp_pair_t *pair) {
  mcgdb_bp_free (pair->temp);
  g_free (pair);
}

gboolean
breakpoints_edit_dialog (const char *filename, long line, int click_y, int click_x) {
  WBlock *bpw        = wblock_empty ();
  WBlock *widget_bps = wblock_empty ();
  int return_val;
  WBlockMain *wbm;
  CalcposData *calcpos_data_bpw, *calcpos_data_bprm;
  GList *pairs = NULL;
  gboolean redraw = FALSE;

  (void) click_x;

  for ( GList *l=mcgdb_bp_find_bp_with_location (mcgdb_bps, filename, line);
        l!=0;
        l = mcgdb_bp_find_bp_with_location (l->next, filename, line))
  {
    bp_pair_t *pair = bp_pair_new (MCGDB_BP (l));
    pairs = g_list_append (pairs, pair);
    wblock_add_widget (widget_bps, bp_widget (&pairs, pair));
  }

  wblock_add_widget (bpw, bpw_prolog (&pairs));
  wblock_add_widget (bpw, wblock_newline ());
  wblock_add_widget (bpw, widget_bps);
  wblock_add_widget (bpw, bpw_epilog (&pairs));

  disable_gdb_events = TRUE;
  wbm = wblock_main_new ();

  calcpos_data_bpw = calcpos_data_new ();
  calcpos_data_bpw->y = click_y;
  calcpos_data_bpw->x = LINE_STATE_WIDTH + 2;
  calcpos_data_bpw->closest_to_y = TRUE;
  calcpos_data_bpw->cols = 40;
  wblock_main_add_widget (wbm, bpw, NULL, calcpos_data_bpw, TRUE);


  calcpos_data_bprm = calcpos_data_new ();
  calcpos_data_bprm->y = click_y;
  calcpos_data_bprm->x = 0;
  calcpos_data_bprm->closest_to_y = FALSE;
  calcpos_data_bprm->cols = LINE_STATE_WIDTH;
  calcpos_data_bprm->lines = 1;
  wblock_main_add_widget (wbm, bprm_widget (pairs), NULL, calcpos_data_bprm, FALSE);

  return_val = wblock_main_run (wbm);
  disable_gdb_events = FALSE;

  if (return_val!=B_CANCEL)
    redraw = bpw_apply_changes (pairs);

  wblock_main_free (wbm);
  g_list_free_full (pairs, (GDestroyNotify) bp_pair_free);

  return redraw;
}
