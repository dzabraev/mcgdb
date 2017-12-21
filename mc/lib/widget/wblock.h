#ifndef __block_widget_h__
#define __block_widget_h__

#include "lib/global.h"
#include "lib/widget.h"
#include "lib/skin.h"

//#include "lib/widget/mouse.h"

#define WBLOCK_COLOR_NORMAL tty_try_alloc_color_pair2 ("black", "white", NULL, FALSE)

typedef struct WBlock WBlock;
typedef struct WBlockMain WBlockMain;
typedef struct WbmWidgetEntry WbmWidgetEntry;

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
typedef void (*wblock_save_cb_t) (WBlock *wb);

#define WBLOCK(p) ((WBlock *)(p))
#define WBLOCK_DATA(l) (l) ? ((WBlock *)((l)->data)) : NULL

#define WBLOCK_DRAW(wb,y0,x0,y,x,lines,cols,do_draw) \
  wb->draw(wb,y0,x0,y,x,lines,cols,do_draw)

#define WBLOCK_REDRAW(wb)        wb->draw(wb,wb->y,wb->x,wb->y,wb->x,wb->lines,wb->cols,TRUE)
#define WBLOCK_UPDATE_COORDS(wb) wb->draw(wb,wb->y,wb->x,wb->y,wb->x,wb->lines,wb->cols,FALSE)
#define WBLOCK_KEY(wb,parm) wb->key(wb,parm)
#define WBLOCK_MOUSE(wb,msg,event) (wb)->mouse(wb,msg,event)
#define WBLOCK_SAVE(wb) (wb)->save(wb)

#define IN_RECTANGLE(y0,x0,y,x,lines,cols) \
((y0)>=(y) && (y0)<(y)+(lines) && (x0)>=(x) && (x0)<(x)+(cols))

#define YX_IN_WIDGET(w,_y,_x) IN_RECTANGLE(_y,_x,(w)->y,(w)->x,(w)->lines,(w)->cols)

typedef struct WBlock {
  WbmWidgetEntry *entry;
  GList *widgets;
  char *name;
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
    int color;
  } style;

  wblock_mouse_cb_t mouse;
  wblock_key_cb_t key;
  wblock_destroy_cb_t destroy;
  wblock_draw_cb_t draw;
  wblock_save_cb_t save;

  int cursor_x;
  int cursor_y;

  gboolean redraw;

  gpointer wdata;
} WBlock;


void wblock_set_mouse   (WBlock *wb, wblock_mouse_cb_t mouse);
void wblock_set_key     (WBlock *wb, wblock_key_cb_t key);
void wblock_set_destroy (WBlock *wb, wblock_destroy_cb_t destroy);
void wblock_set_draw    (WBlock *wb, wblock_draw_cb_t draw);
void wblock_set_save    (WBlock *wb, wblock_save_cb_t save);
void wblock_set_wdata   (WBlock *wb, gpointer wdata);
void wblock_set_color   (WBlock *wb, int color);

WBlock *wblock_new (
  wblock_mouse_cb_t   mouse,
  wblock_key_cb_t     key,
  wblock_destroy_cb_t destroy,
  wblock_draw_cb_t    draw,
  wblock_save_cb_t    save,
  gpointer wdata);

void wblock_init (
  WBlock *wb,
  wblock_mouse_cb_t   mouse,
  wblock_key_cb_t     key,
  wblock_destroy_cb_t destroy,
  wblock_draw_cb_t    draw,
  wblock_save_cb_t    save,
  gpointer wdata);


void wblock_add_widget (WBlock * wb, WBlock * widget);
void wblock_add_const_widget (WBlock * wb, WBlock * widget);


void
wblock_dfl_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw);

void
wblock_dfl_destroy (WBlock *wb);

WBlock *
wblock_get_widget_yx (WBlock *wb, int y, int x);

void
draw_string (
  const char *p,
  int *draw_lines, int *draw_cols,
  int y0, int x0, int y, int x, int lines, int cols,
  gboolean do_draw, gboolean oneline);


void
draw_string_oneline (
  const char *p,
  int *draw_cols,
  int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw);


WbmWidgetEntry * wblock_get_entry (WBlock *wb);
WBlockMain * wblock_get_wbm (WBlock *wb);
WDialog * wblock_get_dialog (WBlock *wb);

WBlock * set_layout (WBlock *wb, layout_t layout);
WBlock * layout_inline (WBlock *wb);
WBlock * wblock_width_auto (WBlock *wb);

WBlock * wblock_empty (void);
WBlock * set_margin (WBlock *wb, int left, int top, int right, int bottom);
WBlock * wblock_newline (void);
WBlock * wblock_nspace (int n);

void wblock_save (WBlock *wb);

void wblock_shift_yx (WBlock *wb, int shift_y, int shift_x);

char * strstrip (const char *str);

void wblock_destroy (WBlock *wb);

WBlock * wblock_set_name (WBlock *wb, char *name);
void wblock_unlink (WBlock *wb);

WBlock * find_closest_by_name (WBlock *wb, const char *name);


#include "wblock-checkbox.h"
#include "wblock-frame.h"
#include "wblock-label.h"
#include "wblock-button.h"
#include "wblock-input.h"
#include "wblock-select.h"

#include "wblock-main.h"

#endif //__block_widget_h__
