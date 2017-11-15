#ifndef __block_widget_h__
#define __block_widget_h__

#include "lib/global.h"
#include "lib/widget.h"

//#include "lib/widget/mouse.h"


typedef struct WBlock WBlock;


typedef void (*pos_callback_t) (int *y, int *x, int *lines, int *cols);

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

typedef enum {
  WIDTH_AUTO = 0,
  //WIDTH_FIXED = 1,
  WIDTH_MAX = 2,
} width_compute_t;

typedef gboolean (*wblock_mouse_cb_t) (WBlock *wb, mouse_msg_t msg, mouse_event_t * event);
typedef gboolean (*wblock_key_cb_t) (WBlock *wb, int parm);
typedef void (*wblock_destroy_cb_t) (WBlock *wb);
typedef void (*wblock_draw_cb_t) (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw);

#define WBLOCK(p) ((WBlock *)(p))
#define WBLOCK_DATA(l) (l) ? ((WBlock *)((l)->data)) : NULL

#define WBLOCK_DRAW(wb,y0,x0,y,x,lines,cols,do_draw) \
  wb->draw(wb,y0,x0,y,x,lines,cols,do_draw)

#define WBLOCK_REDRAW(wb) wb->draw(wb,wb->y,wb->x,wb->y,wb->x,wb->lines,wb->cols,TRUE)
#define WBLOCK_KEY(wb,parm) wb->key(wb,parm)
#define WBLOCK_MOUSE(wb,msg,event) (wb)->mouse(wb,msg,event)
#define WBLOCK_DESTROY(wb) (wb)->destroy(wb)

#define IN_RECTANGLE(y0,x0,y,x,lines,cols) \
((y0)>=(y) && (y0)<(y)+(lines) && (x0)>=(x) && (x0)<(x)+(cols))

#define YX_IN_WIDGET(w,_y,_x) IN_RECTANGLE(_y,_x,(w)->y,(w)->x,(w)->lines,(w)->cols)


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
    width_compute_t width_type;
    int width;
  } style;

  wblock_mouse_cb_t mouse;
  wblock_key_cb_t key;
  wblock_destroy_cb_t destroy;
  wblock_draw_cb_t draw;

  gpointer wdata;
} WBlock;

int
wblock_run (WBlock * wb, pos_callback_t calcpos);

WBlock *wblock_new (
  wblock_mouse_cb_t   mouse,
  wblock_key_cb_t     key,
  wblock_destroy_cb_t destroy,
  wblock_draw_cb_t    draw,
  gpointer wdata);

void wblock_init (
  WBlock *wb,
  wblock_mouse_cb_t   mouse,
  wblock_key_cb_t     key,
  wblock_destroy_cb_t destroy,
  wblock_draw_cb_t    draw,
  gpointer wdata);

void wblock_add_widget (WBlock * wb, WBlock * widget);

void
wblock_dfl_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw);

void
wblock_dfl_destroy (WBlock *wb);

WBlock *
wblock_get_widget_yx (WBlock *wb, int y, int x);

#include "wblock-checkbox.h"
#include "wblock-frame.h"

#endif //__block_widget_h__
