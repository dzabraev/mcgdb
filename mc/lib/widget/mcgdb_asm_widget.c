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
#include "lib/widget/mcgdb_asm_widget.h"

#include "lib/tty/tty.h"
#include "lib/skin.h"

#include "lib/util.h"

#include <jansson.h>




static int asmtab_id;

static void mcgdb_asm_dialog_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event);
static cb_ret_t mcgdb_asm_dialog_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);
static void mcgdb_asm_dialog_gdbevt (WDialog *h);

static void mcgdb_asm_dialog_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
}



static void
mcgdb_asm_dialog_gdbevt (WDialog *h) {
  WTable *wtab;
  struct gdb_action * act = event_from_gdb;
  json_t *pkg = act->pkg;
  event_from_gdb=NULL;

  switch(act->command) {
    case MCGDB_TABLE_ASM:
      wtab = (WTable *)dlg_find_by_id(h,asmtab_id);
      pkg_table_package (pkg,wtab,"asm");
      break;
    default:
      break;
  }

  free_gdb_evt (act);

}



gboolean
is_mcgdb_asm_dialog(WDialog *h) {
  return h->widget.callback==mcgdb_asm_dialog_callback;
}

static cb_ret_t mcgdb_asm_dialog_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  WDialog *h = DIALOG (w);
  WTable  *wtasm;
  switch (msg) {
    case MSG_KEY:
      {
          cb_ret_t ret = MSG_NOT_HANDLED;

          if (parm==EV_GDB_MESSAGE)
          {
            mcgdb_asm_dialog_gdbevt (h);
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
        wtasm = (WTable *) dlg_find_by_id(h, asmtab_id);
        WIDGET(wtasm)->x      =0;
        WIDGET(wtasm)->y      =0;
        WIDGET(wtasm)->lines  =LINES;
        WIDGET(wtasm)->cols   =COLS;
        wtable_update_bound(wtasm);
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



int
mcgdb_asm_dlg(void) {
  WDialog *dlg;
  WTable  *wtasm;

  //int wait_gdb=1;
  //while(wait_gdb) {}

  wtasm = wtable_new (0,0,1,1);
  wtable_add_table(wtasm,"asm",1);
  wtable_set_current_table(wtasm, "asm");
  wtable_update_bound(wtasm);

  dlg = dlg_create (FALSE, 0, 0, 0, 0, WPOS_FULLSCREEN, FALSE, NULL, mcgdb_asm_dialog_callback,
                    mcgdb_asm_dialog_mouse_callback, "[ASM]", NULL);
  add_widget (dlg, wtasm);
  asmtab_id = WIDGET(wtasm)->id;
  dlg_run (dlg);
  return 0;
}
