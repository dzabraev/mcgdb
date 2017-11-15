#ifndef __block_checkbox_h__
#define __block_checkbox_h__

#define CHECKBOX_DATA(p) ((CheckboxData *)(p))

typedef struct CheckboxData {
  gchar *label;
  gboolean *flag;
} CheckboxData;

gboolean wblock_checkbox_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event);
gboolean wblock_checkbox_key (WBlock *wb, int parm);
void wblock_checkbox_destroy (WBlock *wb);

void
wblock_checkbox_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw);


WBlock * wblock_checkbox_new (char *label, gboolean *flag);

#endif