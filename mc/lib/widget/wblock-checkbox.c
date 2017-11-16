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
  wblock_dfl_destroy (wb);
}


void
wblock_checkbox_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  gboolean flag = CHECKBOX_DATA (wb->wdata)->flag[0];
  int draw_cols=0;
  if (!do_draw) {
    wb->lines=1;
    wb->cols=0;
  }
  draw_cols=0;
  draw_string_oneline (flag ? "[x]" : "[ ]", &draw_cols,y0,x0+draw_cols,y,x,lines,cols,do_draw);
  if (!do_draw) {
    wb->cols+=draw_cols;
  }
}

WBlock *
wblock_checkbox_new (gboolean *flag) {
  CheckboxData *data = g_new0 (CheckboxData, 1);
  data->flag = flag;
  return wblock_new (
    wblock_checkbox_mouse,
    wblock_checkbox_key,
    wblock_checkbox_destroy,
    wblock_checkbox_draw,
    data);
}


WBlock *
wblock_checkbox_labeled_new (char *label, gboolean *flag) {
  WBlock *parent = wblock_new (NULL,NULL,NULL,NULL,NULL);
  WBlock *checkbox = wblock_checkbox_new (flag);
  WBlock *checklabel = wblock_label_new (label, TRUE);
  checkbox->style.layout=LAYOUT_INLINE;
  checklabel->style.layout=LAYOUT_INLINE;
  wblock_add_widget (parent, checklabel);
  wblock_add_widget (parent, checkbox);
  return parent;
}
