#ifndef __block_frame_h__
#define __block_frame_h__

#include "lib/global.h"
#include "lib/skin.h" /*EDITOR_NORMAL_COLOR*/


#define WBLOCK_INPUT_COLOR EDITOR_NORMAL_COLOR

#define WBLOCK_INPUT_DATA(p) ((WBlockInputData *)(p))

typedef struct WBlockInputData {
  char **buf;
  int *size;
  int pos; /*cursor position in buf*/
  int offset_y;
  int offset_x;
  int cursor_y;
  int cursor_x;
} WBlockInputData;

WBlock * wblock_input_new (char **buf, int *size);

#endif