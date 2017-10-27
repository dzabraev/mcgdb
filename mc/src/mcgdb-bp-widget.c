#include <config.h>

//#include <glib.h>

//#include "lib/widget/quick.h"
#include "lib/widget.h"

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

#define quick_append(arr,X) do {\
  aquick_widget_t q = (aquick_widget_t) X;\
  g_array_append_val (arr,q);\
} while (0)

static int
add_widget_exists_bp (GArray * bps_widgets, mcgdb_bp *bp) {
  int idx=0;
  //QUICK_LABEL ()
  //widgets[idx++] = (quick_widget_t) QUICK_START_GROUPBOX (N_("breakpoint"));
  //dgets[idx++] = (quick_widget_t) QUICK_START_COLUMNS;
  quick_append (bps_widgets,QUICK_CHECKBOX (strdup(N_("enabled")), &bp->enabled, NULL));
  //widgets[idx++] = (aquick_widget_t) ;
  //dgets[idx++] = (quick_widget_t) QUICK_SEPARATOR (FALSE);
  //dgets[idx++] = (quick_widget_t) QUICK_STOP_COLUMNS;
  //widgets[idx++] = (quick_widget_t) QUICK_STOP_GROUPBOX;
  return idx;
}

gboolean
breakpoints_edit_dialog (const char *filename, long line) {
  int nbps = count_bps (filename,line);
  GArray * bps_widgets = g_array_new (FALSE, FALSE, sizeof(aquick_widget_t));
  mcgdb_bp ** copy_bps = g_new (mcgdb_bp *, nbps);
  quick_dialog_t qdlg;
  int idx=0;
  GList *l;
  mcgdb_bp *bp;

  g_array_set_clear_func (bps_widgets, aquick_free);

  for (l=mcgdb_bp_find_bp_with_location (mcgdb_bps, filename, line);
        l!=0;
        l = mcgdb_bp_find_bp_with_location (l->next, filename, line),idx++) {
    message_assert (l!=0);
    bp = MCGDB_BP (l);
    copy_bps[idx] = mcgdb_bp_copy (bp);
    add_widget_exists_bp (bps_widgets,copy_bps[idx]);
  }
  quick_append (bps_widgets, QUICK_END);
  qdlg = (quick_dialog_t) {
    1, 1, 60, 30,
    N_("Breakpoints"), "[Breakpoints]",
    (quick_widget_t *) bps_widgets->data, NULL, bp_mouse_callback, bp_dlg_draw_broadcast_msg
  };
  quick_dialog (&qdlg);

  /*compare new bps with old bps and get difference*/

  l=mcgdb_bp_find_bp_with_location (mcgdb_bps, filename, line);
  for (int i=0;i<nbps;i++) {
    message_assert (l!=0);
    //MCGDB_BP(l), copy_bps(i)
    l = mcgdb_bp_find_bp_with_location (l, filename, line);
  }

  for (int i=0;i<nbps;i++) {
    mcgdb_bp_free (copy_bps[i]);
  }
  g_free (copy_bps);


  g_array_free (bps_widgets, TRUE);

/*
    gboolean test;
    {
        quick_widget_t quick_widgets[] = {
            QUICK_CHECKBOX (N_("test1"), &test, NULL),
            QUICK_CHECKBOX (N_("test2"), &test, NULL),
            QUICK_CHECKBOX (N_("test3"), &test, NULL),
            QUICK_CHECKBOX (N_("test4"), &test, NULL),
            QUICK_CHECKBOX (N_("test5"), &test, NULL),
            QUICK_CHECKBOX (N_("test6"), &test, NULL),
            QUICK_CHECKBOX (N_("test7"), &test, NULL),
            QUICK_CHECKBOX (N_("test8"), &test, NULL),
            QUICK_CHECKBOX (N_("test9"), &test, NULL),
            QUICK_CHECKBOX (N_("test10"), &test, NULL),
            QUICK_CHECKBOX (N_("test11"), &test, NULL),
            QUICK_END
        };

        quick_dialog_t qdlg = {
            1, 1, 74, 8,
            N_("Breakpoints"), "[Breakpoints]",
            quick_widgets, NULL, bp_mouse_callback, bp_dlg_draw_broadcast_msg
        };


        quick_dialog (&qdlg);
    }
*/

  return TRUE;
}
