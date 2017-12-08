#include <config.h>

#include "lib/widget/wblock.h"
#include "src/mcgdb.h"

select_option_t *
select_option_new (int id, WBlock *wb, gboolean selected, char *short_name) {
  select_option_t *option = g_new0 (select_option_t, 1);
  option->id = id;
  option->wb = wb;
  option->selected=selected;
  option->short_name = short_name;
  return option;
}

void
select_option_destroy (select_option_t *option) {
  g_free (option->short_name);
}


gboolean
select_option_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event) {
  int *selected_id = (int *)wb->parent->wdata;
  int *option_id = (int *)wb->wdata;
  WDialog *h;

  (void) event;

  if (msg!=MSG_MOUSE_CLICK)
    return FALSE;

  selected_id[0] = option_id[0];

  h = wblock_get_dialog (wb);
  h->ret_value = B_ENTER;
  dlg_stop (h);

  return TRUE;
}

int
dialog_wblock_select (GList *options, int y, int x) {
  WBlock *wb = wblock_empty ();
  int selected_id = WBLOCK_CANCEL;
  CalcposData *calcpos_data;
  WBlockMain *wbm;

  wblock_set_wdata (wb, &selected_id);

  for (GList *l = options; l; l=l->next) {
    select_option_t *option = (select_option_t *)(l->data);
    WBlock *row = wblock_empty ();

    if (option->selected==TRUE)
      selected_id = option->id;

    wblock_set_wdata (row, &option->id);
    wblock_set_mouse (row, select_option_mouse);
    wblock_add_const_widget (row, option->wb);
    wblock_add_widget (wb, row);
  }


  wbm = wblock_main_new ();

  calcpos_data = calcpos_data_new (); /*it will be freed in wblock_main_free*/
  calcpos_data->y = y;
  calcpos_data->x = x;
  calcpos_data->closest_to_y = TRUE;
  wblock_main_add_widget (wbm, wb, NULL, calcpos_data, TRUE);

  disable_gdb_events_enter ();
  wblock_main_run (wbm);
  disable_gdb_events_exit ();

  wblock_main_free (wbm);

  return selected_id;
}

void
wblock_button_select_push (WBlock *wb, WBlockButtonData *data) {
  WblockButtonSelectData *user_data = (WblockButtonSelectData *) data->user_data;
  int ret = dialog_wblock_select (user_data->options, wb->y, wb->x+2);
  if (ret != WBLOCK_CANCEL) {
    select_option_t *opt = get_option_by_id (user_data->options, ret);
    wblock_button_setlabel (wb, g_strdup (opt->short_name));
    user_data->option_id[0] = ret;
  }
}


select_option_t *
get_option_by_id (GList *options, int id) {
  for (GList *l=options; l;l=l->next) {
    select_option_t *option = (select_option_t *)(l->data);
    if (option->id==id)
      return option;
  }
  return NULL;
}

void
wblock_button_select_user_data_free (gpointer user_data) {
  WblockButtonSelectData *data = (WblockButtonSelectData *) user_data;
  g_list_free_full (data->options, (GDestroyNotify) select_option_destroy);
  g_free (data);
}

WBlock *
wblock_button_select_new (int *option_id, GList *options) {
  WBlock *wb;
  WblockButtonSelectData *user_data = g_new0 (WblockButtonSelectData,1);
  select_option_t *initial_opt = get_option_by_id (options, option_id[0]);
  user_data->option_id = option_id;
  user_data->options = options;
  wb = wblock_button_new (
    g_strdup(initial_opt ? initial_opt->short_name : g_strdup("[No selected]")),
    wblock_button_select_push,
    user_data,
    wblock_button_select_user_data_free);
  return wb;
}

