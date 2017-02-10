#include <config.h>

#include <ctype.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

#include "lib/global.h"

#include "lib/widget.h"         /* Widget */
#include "lib/widget/widget-common.h"
#include "lib/widget/mouse.h"
#include "lib/widget/dialog.h"

#include "lib/widget/mcgdb_lvarswidget.h"
//#include "lib/widget/listbox.h"

#include "lib/tty/tty.h"
#include "lib/skin.h"

static cb_ret_t lvars_dialog_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);
static cb_ret_t lvars_callback        (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);

static void lvars_dialog_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event);
static void lvars_mouse_callback        (Widget * w, mouse_msg_t msg, mouse_event_t * event);







static cb_ret_t
lvars_dialog_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  //WDialog *h = DIALOG (w);

  switch (msg) {
    default :
      return dlg_default_callback (w, sender, msg, parm, data);
  }
}


static void
lvars_dialog_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
  gboolean unhandled = TRUE;
  event->result.abort = unhandled;
}



Wlvars *
lvars_new (int y, int x, int height, int width)
{
    Wlvars *l;
    Widget *w;

    if (height <= 0)
        height = 1;

    l = g_new (Wlvars, 1);
    w = WIDGET (l);
    widget_init (w, y, x, height, width, lvars_callback, lvars_mouse_callback);
    w->options |= WOP_SELECTABLE | WOP_WANT_HOTKEY;

    return l;
}


static cb_ret_t
lvars_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  cb_ret_t handled = MSG_HANDLED;
  tty_setcolor(EDITOR_NORMAL_COLOR);
  widget_move(w, 0, 0);
  //tty_fill_region(0,0,100,100,' ');
  tty_print_char(parm);

  return handled;
}

static void
lvars_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
}

int
lvarswidget(void) {
  WDialog *lvars_dlg;
  lvars_dlg =
        dlg_create (FALSE, 0, 0, 1, 1, WPOS_FULLSCREEN, FALSE, NULL, lvars_dialog_callback,
                    lvars_dialog_mouse_callback, "[GDB local vars]", NULL);
  add_widget (lvars_dlg, lvars_new (0, 0, 0, 0));
  dlg_run (lvars_dlg);
  return 0;
}


