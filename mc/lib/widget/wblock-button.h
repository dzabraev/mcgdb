#ifndef __wblock_button_h__
#define __wblock_button_h__

struct WBlock;
typedef struct WBlockButtonData WBlockButtonData;

typedef void (*wblock_push_t) (WBlock *wb, WBlockButtonData *data);

#define WBLOCK_BUTTON_COLOR tty_try_alloc_color_pair2 ("black", "white", "bold", FALSE)

#define WBLOCK_BUTTON_DATA(p) ((WBlockButtonData *)(p))

typedef struct WBlockButtonData {
  char *label;
  int npush;
  wblock_push_t push;
  gpointer user_data;
  GDestroyNotify user_data_destroy; /*cleanup for data field*/
  int click_y;
  int click_x;
} WBlockButtonData;


void wblock_button_destroy (WBlock *wb);
gboolean wblock_button_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event);
gboolean wblock_button_key (WBlock *wb, int parm);
void wblock_button_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw);
WBlock *wblock_button_new (char *label, wblock_push_t push, gpointer user_data, GDestroyNotify user_data_destroy);
void wblock_button_setlabel (WBlock *wb, char *label);



void wblock_button_code        (WBlock *wb, int code);
void wblock_button_ok_cb       (WBlock *wb, WBlockButtonData *data);
void wblock_button_cancel_cb   (WBlock *wb, WBlockButtonData *data);

#endif