#ifndef __block_frame_h__
#define __block_frame_h__

#include "lib/global.h"


#define WBLOCK_FRAME_COLOR_NORMAL WBLOCK_COLOR_NORMAL

#define WBLOCK_FRAME_DATA(p) ((WBlockFrameData *)(p))

typedef struct WBlockFrameData {
  char *label;
} WBlockFrameData;


void
wblock_frame_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw);

WBlock * wblock_frame_new (char *label);
#endif
