#ifndef __block_input_h__
#define __block_input_h__

#include "lib/global.h"
#include "lib/skin.h" /*EDITOR_NORMAL_COLOR*/


#define WBLOCK_INPUT_COLOR EDITOR_NORMAL_COLOR

#define WBLOCK_INPUT_DATA(p) ((WBlockInputData *)(p))

typedef struct WBlockInputData {
  GArray *buf;
  int offset_y;
  int offset_x;
  int h_min;
  int h_max;
  char **result;
} WBlockInputData;

WBlock * wblock_input_new (char **initial, int h_min, int h_max);

#endif