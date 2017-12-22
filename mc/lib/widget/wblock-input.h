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
  int w_min;
  int w_max;
  char **result;
  gboolean readonly;
  gboolean disable_enter;
} WBlockInputData;


#define WBLOCK_INPUT_DATA_INTEGER(p) ((WBlockInputDataInteger *)(p))

typedef struct WBlockInputDataInteger {
  WBlockInputData data;
  int *val;
  char *input;
  gboolean non_negative;
} WBlockInputDataInteger;



void wblock_input_set_readonly (WBlock *wb, gboolean ro);

WBlock * wblock_input_new (char **initial, int h_min, int h_max, int w_min, int w_max);
WBlock * wblock_input_integer_new (int *val, gboolean non_negative);

void wblock_input_disable_enter (WBlock *wb, gboolean disable_enter);

void wblock_input_view_toleft (WBlock *wb);
void wblock_input_view_toright (WBlock *wb);

WBlock *wblock_input_clean_button (WBlock *wb_input, char *text);


#endif