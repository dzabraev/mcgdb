

typedef struct {
  int id;
  WBlock *wb;
  gboolean selected;
} select_option_t;

typedef struct {
  int *option_id,
  GList *options;
} WblockButtonSelect;


select_option_t *
select_option_new (int id, WBlock *wb, gboolean selected) {
  select_option_t *option = g_new0 (select_option_t, 1);
  option->id = id;
  option->wb = wb;
  option->selected=selected;
  return option;
}

int
dialog_wblock_select (GList *options, int y, int x) {
  WBlock *wb = wblock_empty ();
  int selected_id = WBLOCK_CANCEL;
  for (GList *l = options; l; l=l->next) {
    select_option_t *option = (select_option_t *)(l->data);
    WBlock *row = wblock_empty ();

    if (option->selected==TRUE)
      selected_id = option->id;

    wblock_set_wdata (row, &selected_id);
    wblock_set_click (row, select_option);
    wblock_append_widget (wb, row);
  }

  disable_gdb_events = TRUE;
  {
    CalcposData *calcpos_data = calcpos_data_new ();
    calcpos_data->y = y;
    calcpos_data->x = x;
    calcpos_data->closest_to_y = TRUE;
    return_val = wblock_run (wb, NULL, calcpos_data);
    calcpos_data_free (calcpos_data);
  }
  disable_gdb_events = FALSE;

  return selected_id
}


WBlock *
wblock_button_select (char *label, int *option_id, GList *options) {
  WBlock *wb;
  WblockButtonSelect *data = g_new0 (WblockButtonSelect,1);
  data->option_id = option_id;
  data->options = options;
  wb = wblock_button (label, button_select_thread_push, data, g_free);
  return wb;
}


















WBlock *
thread_widget_new (thread_entry_t *t) {
  WBlock *wb = wblock_empty ();
  wblock_widget_append (wb,
    layout_inline (wblock_label_new (
      g_strdup_printf ("#%d", t->global_num), FALSE
  )));
  wblock_widget_append (wb, wblock_nspace (1));
  wblock_widget_append (wb,
    layout_inline (wblock_label_new (
      g_strdup (t->name), FALSE
  )));
  wblock_widget_append (wb,
    wblock_label_new (
      g_strdup_printf ("pid=%d tid=%d lwp=%d", t->global_num), FALSE
  ));
  return wb;
}


GList *
get_setect_options_for_threads (int initial_id, gboolean add_none) {
  GList *options = NULL;

  if (add_none) {
    WBlock *wb_none = wblock_label_new (g_strdup ("None"), FALSE);
    options = g_list_append (options,select_option_new (-1, wb_none, -1));
  }

  for (GList *tl=thread_list;tl;tl=tl->next) {
    gboolean selected;
    WBlock *row = wblock_frame_new ();
    thread_entry_t *t = (thread_entry_t *)tl->data;
    wblock_append_widget (row, thread_widget_new (t));
    selected = t->global_num==initial_id;
    if (selected) {
      wblock_frame_setcolor (row, SELECTED_THREAD_COLOR);
    }
    options = g_list_append (options, select_option_new (t->global_num, row, selected));
  }
  return options;
}


WBlock *
wblock_button_select_thread (int *global_num, gboolean add_none) {
  thread_entry_t *t=get_thread_by_global_num (global_num[0]);
  char *label;
  if (t) {
    label = g_strdup_printf ("#%d %s", t->global_num, t->name);
  }
  else {
    label = g_strdup ("No thread selected");
  }

  return wblock_button_select (label, global_num, get_setect_options_for_threads (global_num[0], add_none));
}
 