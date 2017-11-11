#include "block-widget.h"


gboolead
wb_checkbox_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event) {
  gboolean *flag = CHECKBOX_DATA (wb->wdata)->flag;
  flag[0] = !flag[0];
  WBLOCK_REDRAW (wb);
  return TRUE;    
}


gboolean
wb_checkbox_key (WBlock *wb, int parm) {
  return FALSE;
}

void
wb_checkbox_destroy (WBlock *wb) {
  g_free (CHECKBOX_DATA (wb->wdata)->label);
  wblock_dfl_destroy (wb);
}

void
wb_checkbox_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  int x_line=x0;
  const char * p = CHECKBOX_DATA (wb->wdata)->label;
  wb->lines=1;
  wb->cols=0;
  while (*p) {
	if (IN_RECTANGLE (y0,x_line,y,x,lines,cols)) {
	  x_line++;
	  wb->cols++;
	  if (do_draw) {
		tty_gotoyx (y0, x_line);
		tty_print_char (*p);
	  }
	}
	p++;
  }
}

WBlock *
wb_checkbox_new (char *label, gboolean *flag) {
  CheckboxData *data = g_new (CheckboxData, 1);
  data->label = label;
  data->flag = flag;
  return wblock_new (
	wb_checkbox_mouse,
	wb_checkbox_key,
	wb_checkbox_destroy,
	wb_checkbox_draw,
	data);
}