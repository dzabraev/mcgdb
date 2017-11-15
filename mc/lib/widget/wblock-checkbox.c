#include <config.h>
#include "lib/global.h"
#include "lib/tty/tty.h"


#include "wblock.h"


gboolean
wblock_checkbox_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event) {
  gboolean *flag = CHECKBOX_DATA (wb->wdata)->flag;
  flag[0] = !flag[0];
  WBLOCK_REDRAW (wb);
  return TRUE;
}


gboolean
wblock_checkbox_key (WBlock *wb, int parm) {
  return FALSE;
}

void
wblock_checkbox_destroy (WBlock *wb) {
  g_free (CHECKBOX_DATA (wb->wdata)->label);
  wblock_dfl_destroy (wb);
}


void
wblock_checkbox_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  int x_line=x0;
  const char *label = CHECKBOX_DATA (wb->wdata)->label;
  gboolean flag = CHECKBOX_DATA (wb->wdata)->flag[0];
  wb->lines=1;
  wb->cols=0;
  draw_string_oneline (label, &wb->cols,y0,x0,y,x,lines,cols,do_draw);
  wb->cols+=1;
  draw_string_oneline (flag ? "[x]" : "[ ]", &wb->cols,y0,x0+wb->cols,y,x,lines,cols,do_draw);
}

WBlock *
wblock_checkbox_new (char *label, gboolean *flag) {
  CheckboxData *data = g_new (CheckboxData, 1);
  data->label = label;
  data->flag = flag;
  return wblock_new (
    wblock_checkbox_mouse,
    wblock_checkbox_key,
    wblock_checkbox_destroy,
    wblock_checkbox_draw,
    data);
}