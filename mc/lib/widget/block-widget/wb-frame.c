#include "block-widget.h"

void
wb_frame_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  if (do_draw) {
	int x1,y1,lines1,cols1;
	if (x0 < x)
	  lines1 = lines - (x-x0)
	tty_fill_region (y,x,lines,cols,' ');
	tty_	
  }
  wblock_dfl_draw (wb, y0+1, x0+1, y+1, x+1, lines-2, cols-2, do_draw);
}

WBlock *
wb_frame_new (char *label) {
  CheckboxData *data = g_new (FrameData, 1);
  data->label = label;
  data->color = EDITOR_NORMAL_COLOR;
  WblockFrame *wbf = g_new0 (WblockFrame, 1);
  wblock_init (&wbf->wb, NULL, NULL, NULL, wb_frame_draw, data);
  return wbf;
}
