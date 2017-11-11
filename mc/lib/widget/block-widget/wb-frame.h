#ifndef __block_frame_h__
#define __block_frame_h__

#define FRAME_DATA(p) ((FrameData *)(p))

typedef struct FrameData {
  gchar *label;
  int color;
} FrameData;


WBlock * wb_frame_new (char *label);

#endif