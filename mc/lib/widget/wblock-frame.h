#ifndef __block_frame_h__
#define __block_frame_h__

#include "lib/global.h"

#define FRAME_DATA(p) ((FrameData *)(p))

typedef struct FrameData {
  gchar *label;
  int color;
} FrameData;


void
wb_frame_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw);

WBlock * wb_frame_new (char *label);

#endif