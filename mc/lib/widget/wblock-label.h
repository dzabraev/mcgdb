#ifndef __wblock_label_h__
#define __wblock_label_h__

#define WBLOCK_LABEL_DATA(p) ((WBlockLabelData *)(p))

typedef struct WBlockLabelData {
  gchar *label;
} WBlockLabelData;

#define WBLOCK_MULTILABEL_DATA(p) ((WBlockMultilabelData*)(p))

typedef struct WBlockMultiLabelData {
  GList *labels; /* char * */
  int current;
  gboolean oneline;
} WBlockMultilabelData;

void wblock_label_destroy (WBlock *wb);
void wblock_multilabel_destroy (WBlock *wb);

void
wblock_label_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw);

void
wblock_label_oneline_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw);

gboolean
wblock_multilabel_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event);

void
wblock_multilabel_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw);


WBlock * wblock_label_new (char *label, gboolean oneline);
WBlock * wblock_multilabel_new (gboolean oneline, ...);


#endif