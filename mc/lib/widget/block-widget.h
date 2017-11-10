#ifndef __block_widget_h__
#define __block_widget_h__

#include <config.h>

struct WBlock;


typedef void (*pos_callback_t) (Widget *w);

typedef enum {
  ALIGN_LEFT=0,
  ALIGN_CENTER,
  ALIGN_RIGHT,
} align_t;

typedef enum {
  LAYOUT_BLOCK=0,
  LAYOUT_INLINE,
} layout_t;

typedef struct {
  int x0;
  int y0;
  int x;
  int y;
  int lines;
  int cols;
} draw_data_t;

#define WBLOCK(l) (l) ? ((WBlock *)((l)->data)) : NULL
#define WBLOCK_DRAW(wb,y0,x0,y,x,lines,cols) wb->draw(wb,y0,x0,y,x,lines,cols)
#define WBLOCK_CALCSIZE(wb,y0,x0,y,x,lines,cols) wb->calc_size(wb,y0,x0,y,x,lines,cols)
#define WBLOCK_KEY(wb,parm) wb->key(wb,parm)
#define WBLOCK_MOUSE(wb,msg,event) (wb)->mouse_callback(wb,msg,event)
#define WBLOCK_DESTROY(wb) (wb)->destroy(wb)

typedef gboolead (*wblock_mouse_cb_t) (WBlock *wb, mouse_msg_t msg, mouse_event_t * event);
typedef gboolead (*wblock_key_cb_t) (WBlock *wb, int parm);
typedef void (*wblock_destroy_cb_t) (WBlock *wb);
typedef void (*wblock_draw_cb_t) (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols);
typedef void (*wblock_calc_size_cb_t) (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols);


typedef struct WBlock {
  GList *widgets;
  //Garray *coord; /* triplets (xl,xr,y) */
  int y;
  int x;
  int lines;
  int cols;
  WBlock *parent;
  struct {
    align_t align;
    layout_t layout;
    struct {
      int left;
      int top;
      int right;
      int bottom;
    } margin;
  } style;

  wblock_mouse_cb_t mouse;
  wblock_key_cb_t key;
  wblock_destroy_cb_t destroy;
  wblock_draw_cb_t draw;
  wblock_calc_size_cb_t calc_size;

  gpointer wdata;
} WBlock;

WBlock * wblock_new (wblock_cb_t callback, wblock_mouse_cb_t mouse_callback, gpointer wdata);
void wblock_free (WBlock * wb);
void wblock_add_widget (WBlock * wb, WBlock * widget);
void wblock_run (WBlock * wb);

typedef struct CheckboxData {
  gchar *label;
  gboolean *flag;
} CheckboxData;

#endif __block_widget_h__
