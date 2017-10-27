#include <config.h>

//#include <glib.h>

//#include "lib/widget/quick.h"
#include "lib/widget.h"
#include "lib/tty/tty.h"        /* LINES, COLS */

#include "src/mcgdb.h"
#include "src/mcgdb-bp.h"
#include "src/mcgdb-bp-widget.h"


static void
bp_dlg_draw_broadcast_msg(WDialog * h);

static void
bp_mouse_callback(Widget * w, mouse_msg_t msg, mouse_event_t * event) {
  int shift_y=0;
  switch (msg) {
    case MSG_MOUSE_SCROLL_UP:
        shift_y = 2;
        break;

    case MSG_MOUSE_SCROLL_DOWN:
        shift_y = -2;
        break;

    default:
      if (event->y < w->y+1 || event->y > w->y+w->lines-2)
        return;
  }

  if (DIALOG(w)->widgets) {
    Widget  *wf = (Widget *)(DIALOG(w)->widgets->data),
            *wl = (Widget *)(g_list_last (DIALOG(w)->widgets)->data);
    int C = w->y+2, D = w->y + w->lines - 2, B=wf->y, A=wl->y+wl->lines;
    if (shift_y>0)
      shift_y = MIN(shift_y,C-B);
    else
      shift_y = MAX(D-A,shift_y);

    if (wf->y+shift_y > w->y+3)
      shift_y=0;
    if (wl->y+wl->lines < w->y+w->lines-3)
      shift_y=0;
  }


  if (shift_y) {
    send_message (w, NULL, MSG_DRAW, 0, NULL);
    WDialog * h = DIALOG(w);
    for(GList *l = h->widgets; l!=NULL; l = g_list_next (l)) {
      Widget *c = (Widget *)(l->data);
      c->y+=shift_y;
    }
    bp_dlg_draw_broadcast_msg (h);
  }

  event->result.abort = TRUE;
}

static void
bp_dlg_draw_broadcast_msg(WDialog * h) {
  GList *h_current_svd=h->current;
  h->current=NULL;
  for(GList *l = h->widgets; l!=NULL; l = g_list_next (l)) {
    Widget *c = (Widget *)(l->data);
    Widget *w = WIDGET(h);
    if (c->y+c->lines < w->y+3 || w->y+w->lines-3<c->y) {
      c->state |= WST_DISABLED;
      continue;
    }
    else {
      c->state &= ~WST_DISABLED;
      if (!h->current)
        h->current = l;
      send_message (c, h, MSG_DRAW, 0, NULL);
    }
  }
  if (!h->current)
    h->current = h_current_svd;
}

typedef struct mcgdb_bp_user_input {
  gboolean enabled;
  gboolean silent;
  //char *ign_count_text;
  char *ign_count_result;
  //char *thread_text;
  char *thread_result;
  //char *condition_text;
  char *condition_result;
  //char *commands_text;
  char *commands_result;

  gboolean temporary;
  int hit_count;
  int number;
  GList *locations;
} mcgdb_bp_user_input;

static void
mcgdb_bp_user_input_init (mcgdb_bp_user_input *bp_ui, const mcgdb_bp *bp) {
    bp_ui->temporary = bp->temporary;
    bp_ui->hit_count = bp->hit_count;
    bp_ui->number    = bp->number;
    bp_ui->locations = bp->locations;
    bp_ui->enabled   = bp->enabled;
    bp_ui->silent    = bp->silent;

    //asprintf(&bp_ui->ign_count_text,"%d",bp->ignore_count);
    asprintf(&bp_ui->ign_count_result,"%d",bp->ignore_count);

    //asprintf(&bp_ui->thread_text,"%d",bp->thread);
    asprintf(&bp_ui->thread_result,"%d",bp->thread);

    if (bp->condition) {
      //asprintf(&bp_ui->condition_text,"%s",bp->condition);
      asprintf(&bp_ui->condition_result,"%s",bp->condition);
    }
    else {
      //bp_ui->condition_text = NULL;
    } bp_ui->condition_result = NULL;

    if (bp->commands) {
      //asprintf(&bp_ui->commands_text,"%s",bp->commands);
      asprintf(&bp_ui->commands_result,"%s",bp->commands);
    }
    else {
      //bp_ui->commands_text = NULL;
      bp_ui->commands_result = NULL;
    }
}

static void
mcgdb_bp_user_input_free (mcgdb_bp_user_input *bp_ui) {
  //g_free (bp_ui->ign_count_text);
  g_free (bp_ui->ign_count_result);
  //g_free (bp_ui->thread_text);
  g_free (bp_ui->thread_result);
  //g_free (bp_ui->condition_text);
  g_free (bp_ui->condition_result);
  //g_free (bp_ui->commands_text);
  g_free (bp_ui->commands_result);
}

#define quick_append(arr,X) do {\
  aquick_widget_t q = (aquick_widget_t) X;\
  g_array_append_val (arr,q);\
} while (0)

const char *
n_keep_slash (const char *str, int keep) {
  const char *p=str+1,*q=str;
  while (keep--) {
    p = strchr(p+1,'/');
    if (!p)
      return q+1;
  }
  p = strchr(p+1,'/');
  while (p) {
    q = strchr(q+1,'/');
    p = strchr(p+1,'/');
  }
  return q+1;
}

static void
add_widget_exists_bp (GArray * bps_widgets, mcgdb_bp_user_input *bp) {
  char *str;
  if (!bp->temporary)
    asprintf(&str,"  Breakpoint %d",bp->number);
  else
    asprintf(&str,"  Breakpoint %d (tmp)",bp->number);
  //quick_append (bps_widgets,QUICK_LABEL (str,NULL));
  quick_append (bps_widgets,QUICK_START_GROUPBOX (str));
  quick_append (bps_widgets,QUICK_LABEL (strdup ("Locations:"),NULL));
  for (GList *l = bp->locations;l;l = g_list_next (l)) {
    bp_loc_t * loc = BP_LOC(l);
    asprintf(&str,"%s:%d",n_keep_slash(loc->filename,1),loc->line);
    quick_append (bps_widgets,QUICK_LABEL (str,NULL));
  }
  if (!bp->temporary)
    asprintf(&str,"hit_count %d",bp->hit_count);
  quick_append (bps_widgets,QUICK_LABEL (str,NULL));
  quick_append (bps_widgets,QUICK_CHECKBOX (strdup(N_("enabled")), &bp->enabled, NULL));
  quick_append (bps_widgets,QUICK_CHECKBOX (strdup(N_("silent")), &bp->silent, NULL));
  quick_append (bps_widgets,QUICK_LABELED_INPUT (
      strdup(N_("ign_count")),
      input_label_left,
      strdup(bp->ign_count_result),
      "bp-hit-count",
      &bp->ign_count_result, NULL, FALSE, FALSE, INPUT_COMPLETE_NONE
    ));

  quick_append (bps_widgets,QUICK_STOP_GROUPBOX);
}


int
bp_quick_dialog_skip (quick_dialog_t * quick_dlg, int nskip)
{
  quick_dialog_self self = {0};
  self.quick_dlg = quick_dlg;
  self.nskip = nskip;

  quick_dialog_skip_init (&self);
  WIDGET(self.dd)->pos_flags = WPOS_KEEP_CONST;
  quick_dialog_skip_run (&self);
  quick_dialog_skip_after (&self);

  return self.return_val;
}


gboolean
breakpoints_edit_dialog (const char *filename, long line) {
  int nbps = count_bps (filename,line);
  GArray *bps_widgets = g_array_new (FALSE, FALSE, sizeof(aquick_widget_t));
  mcgdb_bp_user_input *bps_uinp = g_new (mcgdb_bp_user_input, nbps);
  quick_dialog_t qdlg;
  int idx=0;
  GList *l;
  mcgdb_bp *bp;

  g_array_set_clear_func (bps_widgets, (GDestroyNotify) aquick_free);

  for (l=mcgdb_bp_find_bp_with_location (mcgdb_bps, filename, line);
        l!=0;
        l = mcgdb_bp_find_bp_with_location (l->next, filename, line),idx++) {
    message_assert (l!=0);
    bp = MCGDB_BP (l);
    mcgdb_bp_user_input_init (&bps_uinp[idx], bp);
    add_widget_exists_bp (bps_widgets,&bps_uinp[idx]);
    if (l->next) {
      quick_append (bps_widgets,QUICK_SEPARATOR (FALSE));
    }
  }
  quick_append (bps_widgets, QUICK_END);
  qdlg = (quick_dialog_t) {
    3, 9, 60, MAX(MIN(30,LINES-5),3),
    N_("Breakpoints"), "[Breakpoints]",
    (quick_widget_t *) bps_widgets->data, NULL, bp_mouse_callback, bp_dlg_draw_broadcast_msg
  };
  message_assert (idx==nbps);

  bp_quick_dialog_skip (&qdlg,0);

  /*compare new bps with old bps and get difference*/

  l=mcgdb_bp_find_bp_with_location (mcgdb_bps, filename, line);
  for (int i=0;i<nbps;i++) {
    message_assert (l!=0);
    //MCGDB_BP(l), copy_bps(i)
    l = mcgdb_bp_find_bp_with_location (l, filename, line);
  }

  for (int i=0;i<nbps;i++) {
    mcgdb_bp_user_input_free (&bps_uinp[i]);
  }
  g_free (bps_uinp);


  g_array_free (bps_widgets, TRUE);

  return TRUE;
}
