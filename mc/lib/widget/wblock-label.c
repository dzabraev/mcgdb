#include <config.h>

#include "lib/widget/wblock.h"

void
wblock_label_destroy (WBlock *wb) {
  g_free (WBLOCK_LABEL_DATA (wb->wdata)->label);
}

void
wblock_label_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  const char * label = WBLOCK_LABEL_DATA (wb->wdata)->label;
  wb->lines = 0;
  wb->cols = 0;
  draw_string (label, &wb->lines, &wb->cols, y0, x0, y, x, lines, cols, do_draw, FALSE);
}

void
wblock_label_oneline_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  const char * label = WBLOCK_LABEL_DATA (wb->wdata)->label;
  wb->lines=1;
  wb->cols=0;
  draw_string_oneline (label, &wb->cols, y0, x0, y, x, lines, cols, do_draw);
}


WBlock *
wblock_label_new (char *label, gboolean oneline) {
  WBlock *wb = g_new0 (WBlock, 1);
  WBlockLabelData *data = g_new (WBlockLabelData, 1);
  data->label = label;
  wblock_init (wb, NULL, NULL, NULL,
    oneline ? wblock_label_oneline_draw : wblock_label_draw, NULL,
    data);
  return wb;
}


gboolean
wblock_multilabel_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event) {
  WBlockMultilabelData *data = WBLOCK_MULTILABEL_DATA (wb->wdata);
  int total = g_list_length (data->labels);
  int saved = data->current;

  (void) event;

  if (msg!=MSG_MOUSE_CLICK)
    return FALSE;
  data->current = (data->current+1) % total;
  wb->redraw = saved!=data->current;
  return TRUE;
}


void
wblock_multilabel_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  WBlockMultilabelData *data = WBLOCK_MULTILABEL_DATA (wb->wdata);
  const char * label = (const char *) (g_list_nth (data->labels, data->current)->data);
  wb->lines = 0;
  wb->cols = 0;
  draw_string (label, &wb->lines, &wb->cols, y0, x0, y, x, lines, cols, do_draw, data->oneline);
}

WBlock *
wblock_multilabel_new (gboolean oneline, ...) {
  WBlock *wb = g_new0 (WBlock, 1);
  WBlockMultilabelData *data = g_new0 (WBlockMultilabelData, 1);
  va_list labels;
  va_start(labels,oneline);
  data->current=0;
  data->oneline=oneline;
  for (;;) {
    char *label = va_arg(labels,char *);
    if (!label)
      break;
    data->labels = g_list_append (data->labels, label);
  }
  wblock_init (wb, wblock_multilabel_mouse, NULL, NULL,
    wblock_multilabel_draw, NULL, data);
  return wb;
}
