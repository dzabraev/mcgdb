#include <config.h>
#include "lib/global.h"
#include "lib/tty/tty.h"


#include "wblock.h"

void
wblock_button_destroy (WBlock *wb) {
  WBlockButtonData *data = WBLOCK_BUTTON_DATA (wb->wdata);
  if (data->user_data_destroy)
    data->user_data_destroy (data->user_data);
  g_free (data->label);
  g_free (wb->wdata);
  wblock_dfl_destroy (wb);
}

gboolean
wblock_button_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event) {
  WBlockButtonData *data = WBLOCK_BUTTON_DATA (wb->wdata);
  (void) event;

  if (msg!=MSG_MOUSE_CLICK)
    return FALSE;

  data->push (wb, data);
  data->npush++;

  return TRUE;
}

gboolean
wblock_button_key (WBlock *wb, int parm) {
  (void) wb;
  (void) parm;
  return FALSE;
}

void
wblock_button_code (WBlock *wb, int code) {
  WDialog *h = wblock_get_dialog (wb);
  h->ret_value = code;
  dlg_stop (h);
}

void
wblock_button_ok_cb (WBlock *wb, WBlockButtonData *data) {
  (void) data;
  wblock_button_code (wb, B_ENTER);
}

void
wblock_button_cancel_cb (WBlock *wb, WBlockButtonData *data) {
  (void) data;
  wblock_button_code (wb, B_CANCEL);
}



void
wblock_button_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  WBlockButtonData *data = WBLOCK_BUTTON_DATA (wb->wdata);
  int draw_cols=0;
  if (!do_draw) {
    wb->lines=1;
    wb->cols=0;
  }
  draw_cols=0;
  draw_string_oneline (data->label, &draw_cols,y0,x0+draw_cols,y,x,lines,cols,do_draw);
  if (!do_draw) {
    wb->cols+=draw_cols;
  }
}

void
wblock_button_setlabel (WBlock *wb, char *label) {
  WBlockButtonData *data = WBLOCK_BUTTON_DATA (wb->wdata);
  g_free (data->label);
  data->label = label;
  wb->redraw = TRUE;
}


WBlock *
wblock_button_new (char *label, wblock_push_t push, gpointer user_data, GDestroyNotify user_data_destroy) {
  WBlock *wb;
  WBlockButtonData *data = g_new0 (WBlockButtonData, 1);
  data->label = label;
  data->push = push;
  data->user_data = user_data;
  data->user_data_destroy = user_data_destroy;
  wb = wblock_new (
    wblock_button_mouse,
    wblock_button_key,
    wblock_button_destroy,
    wblock_button_draw,
    NULL,
    data);
  wblock_set_color (wb, WBLOCK_BUTTON_COLOR);
  return wb;
}
