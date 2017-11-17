#include <config.h>
#include "lib/global.h"
#include "lib/tty/tty.h"


#include "wblock.h"

void
wblock_button_destroy (WBlock *wb) {
  WBlockButtonData *data = WBLOCK_BUTTON_DATA (wb->wdata);
  g_free (data->data);
  wblock_dfl_destroy (wb);
}

gboolean
wblock_button_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event) {
  WBlockButtonData *data = WBLOCK_BUTTON_DATA (wb->wdata);
  (void) event;

  if (msg!=MSG_MOUSE_CLICK)
    return FALSE;

  data->push (wb, data->data);
  data->npush++;

  return TRUE;
}

gboolean
wblock_button_key (WBlock *wb, int parm) {
  return FALSE;
}


void
wblock_button_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  const char *label = WBLOCK_BUTTON_DATA (wb->wdata)->label;
  int draw_cols=0;
  if (!do_draw) {
    wb->lines=1;
    wb->cols=0;
  }
  draw_cols=0;
  draw_string_oneline (label, &draw_cols,y0,x0+draw_cols,y,x,lines,cols,do_draw);
  if (!do_draw) {
    wb->cols+=draw_cols;
  }
}


WBlock *
wblock_button_new (char *label, wblock_push_t push, gpointer user_data) {
  WBlockButtonData *data = g_new0 (WBlockButtonData, 1);
  data->label = label;
  data->push = push;
  data->data = user_data;
  return wblock_new (
    wblock_button_mouse,
    wblock_button_key,
    wblock_button_destroy,
    wblock_button_draw,
    data);

}
