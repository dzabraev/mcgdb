#include <config.h>
#include <assert.h>

#include <ctype.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>
#include <stdarg.h>


#include "lib/global.h"

#include "lib/widget.h"         /* Widget */
#include "lib/widget/widget-common.h"
#include "lib/widget/mouse.h"
#include "lib/widget/dialog.h"
#include "lib/tty/key.h"

#include "src/mcgdb.h"
#include "lib/widget/wtable.h"
#include "lib/widget/mcgdb_aux_widget.h"
#include "src/keybind-defaults.h"


#include "lib/tty/tty.h"
#include "lib/skin.h"

#include "lib/util.h"

#include <jansson.h>



#define VARS_REGS_WIDGET_X      0
#define VARS_REGS_WIDGET_Y      0
#define VARS_REGS_WIDGET_LINES  (LINES)
#define VARS_REGS_WIDGET_COLS   (COLS/2)


#define BT_TH_WIDGET_X      (COLS/2)
#define BT_TH_WIDGET_Y      0
#define BT_TH_WIDGET_LINES  (LINES)
#define BT_TH_WIDGET_COLS   (COLS-BT_TH_WIDGET_X)



static int VARS_REGS_TABLE_ID;
static int BT_TH_TABLE_ID;

int color_selected_frame;

static cb_ret_t mcgdb_aux_dialog_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);

static void mcgdb_aux_dialog_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event);



static void
mcgdb_aux_dialog_gdbevt (WDialog *h) {
  WTable *wtab_vars_regs = (WTable *)dlg_find_by_id(h, VARS_REGS_TABLE_ID),
         *wtab_bt_th = (WTable *)dlg_find_by_id(h, BT_TH_TABLE_ID),
         *wtab=NULL;
  struct gdb_action * act = event_from_gdb;
  json_t *pkg = act->pkg;
  const char *tabname;
  event_from_gdb=NULL;

  switch(act->command) {
    case MCGDB_EXIT:
      break;
    default:
      tabname = json_str (pkg,"table_name");
      if (wtable_get_table(wtab_vars_regs,tabname)) {
        wtab=wtab_vars_regs;
      }
      else if (wtable_get_table(wtab_bt_th,tabname)) {
        wtab=wtab_bt_th;
      }
      message_assert (wtab!=NULL);
      wtable_gdbevt_common (wtab, act);
      break;
  }

  free_gdb_evt (act);
}



gboolean
is_mcgdb_aux_dialog(WDialog *h) {
  return h->widget.callback==mcgdb_aux_dialog_callback;
}

static cb_ret_t
mcgdb_aux_dialog_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  WDialog *h = DIALOG (w);
  WTable  *vars_regs_table, *bt_th_table;
  switch (msg) {
    case MSG_KEY:
      {
          cb_ret_t ret = MSG_NOT_HANDLED;

          if (parm==EV_GDB_MESSAGE) {
            mcgdb_aux_dialog_gdbevt (h);
            ret = MSG_HANDLED;
          }
          return ret;
      }
    case MSG_DRAW:
      {
        return MSG_HANDLED;
      }
    case MSG_RESIZE:
      {
        w->lines = LINES;
        w->cols = COLS;
        vars_regs_table = (WTable *) dlg_find_by_id(h, VARS_REGS_TABLE_ID);
        WIDGET(vars_regs_table)->x      =VARS_REGS_WIDGET_X;
        WIDGET(vars_regs_table)->y      =VARS_REGS_WIDGET_Y;
        WIDGET(vars_regs_table)->lines  =VARS_REGS_WIDGET_LINES;
        WIDGET(vars_regs_table)->cols   =VARS_REGS_WIDGET_COLS;
        wtable_update_bound(vars_regs_table);

        bt_th_table = (WTable *) dlg_find_by_id(h, BT_TH_TABLE_ID);
        WIDGET(bt_th_table)->x      =   BT_TH_WIDGET_X;
        WIDGET(bt_th_table)->y      =   BT_TH_WIDGET_Y;
        WIDGET(bt_th_table)->lines  =   BT_TH_WIDGET_LINES;
        WIDGET(bt_th_table)->cols   =   BT_TH_WIDGET_COLS;
        wtable_update_bound(bt_th_table);


        return MSG_HANDLED;
      }
    case MSG_INIT:
      break;
    default:
      {
        return dlg_default_callback (w, sender, msg, parm, data);
      }
  }
  return MSG_HANDLED;
}


static void
mcgdb_aux_dialog_mouse_callback (__attribute__((unused)) Widget *  w, 
    __attribute__((unused)) mouse_msg_t msg, mouse_event_t * event) {
  gboolean unhandled = TRUE;
  event->result.abort = unhandled;
}



int
mcgdb_aux_dlg(void) {
  WDialog *aux_dlg;
  WTable  *vars_regs_table, *bt_th_table;

  //int wait_gdb=1;
  //while(wait_gdb) {}

  color_selected_frame = tty_try_alloc_color_pair2 ("red", "black", "bold", FALSE);

  vars_regs_table = wtable_new (
    VARS_REGS_WIDGET_Y,
    VARS_REGS_WIDGET_X,
    VARS_REGS_WIDGET_LINES,
    VARS_REGS_WIDGET_COLS
  );
  wtable_add_table(vars_regs_table,"localvars",mcgdb_aux_map);
  wtable_add_table(vars_regs_table,"registers",mcgdb_aux_map);
  wtable_set_tab(vars_regs_table,"localvars");
  wtable_update_bound(vars_regs_table);

  bt_th_table = wtable_new (
    BT_TH_WIDGET_Y,
    BT_TH_WIDGET_X,
    BT_TH_WIDGET_LINES,
    BT_TH_WIDGET_COLS
  );
  wtable_add_table (bt_th_table,"backtrace",mcgdb_aux_map);
  wtable_add_table (bt_th_table,"threads",mcgdb_aux_map);
  wtable_set_tab (bt_th_table,"backtrace");
  wtable_update_bound(bt_th_table);

  aux_dlg = dlg_create (FALSE, 0, 0, 0, 0, WPOS_FULLSCREEN, FALSE, NULL, mcgdb_aux_dialog_callback,
                    mcgdb_aux_dialog_mouse_callback, "[GDB]", NULL);
  add_widget (aux_dlg, vars_regs_table);
  add_widget (aux_dlg, bt_th_table);
  VARS_REGS_TABLE_ID    =   WIDGET(vars_regs_table)->id;
  BT_TH_TABLE_ID        =   WIDGET(bt_th_table)->id;
  dlg_run (aux_dlg);
  return 0;
}

