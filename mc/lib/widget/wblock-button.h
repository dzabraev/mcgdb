#ifndef __wblock_button_h__
#define __wblock_button_h__

struct WBlock;

typedef void (*wblock_push_t) (WBlock *wb, gpointer data);


#define WBLOCK_BUTTON_DATA(p) ((WBlockButtonData *)(p))

typedef struct WBlockButtonData {
  char *label;
  int npush;
  wblock_push_t push;
  gpointer data;
  GDestroyNotify destroy; /*cleanup for data field*/
} WBlockButtonData;


void wblock_button_destroy (WBlock *wb);
gboolean wblock_button_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event);
gboolean wblock_button_key (WBlock *wb, int parm);
void wblock_button_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw);
WBlock *wblock_button_new (char *label, wblock_push_t push, gpointer data, GDestroyNotify destroy);
void wblock_button_setlabel (WBlock *wb, char *label);


void wblock_button_code     (WBlock *wb, int code);
void wblock_button_ok       (WBlock *wb, gpointer data);
void wblock_button_cancel   (WBlock *wb, gpointer data);

#endif