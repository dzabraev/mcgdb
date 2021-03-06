#ifndef __wblock_select_h__
#define __wblock_select_h__

#include "lib/tty/color.h"

#define SELECTED_THREAD_COLOR tty_try_alloc_color_pair2 ("red", "cyan", 0, 0)
#define WBLOCK_CANCEL -2


typedef struct {
  int id;
  WBlock *wb;
  gboolean selected;
  char *short_name;
  char **label;
} select_option_t;

typedef struct {
  int *option_id;
  GList *options;
} WblockButtonSelectData;

select_option_t * select_option_new (int id, WBlock *wb, gboolean selected, char *short_name);
void select_option_destroy (select_option_t *option);
select_option_t *get_option_by_id (GList *options, int id);

gboolean select_option_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event);
int dialog_wblock_select (GList *options, int y, int x);
void wblock_button_select_push (WBlock *wb, WBlockButtonData *data);
void wblock_button_select_user_data_free (gpointer user_data);

WBlock * wblock_button_select_new (int *option_id, GList *options);


#endif