#include <config.h>

#include "lib/global.h"
#include <strings.h>
#include "src/keybind-defaults.h" /*bpw_map*/
#include "src/mcgdb.h"
#include "lib/widget/wblock.h"
#include "lib/skin.h" /*EDITOR_NORMAL_COLOR*/
#include "lib/tty/tty.h"


static gboolean wbm_exists_redraw (WBlockMain * wbm);

static gboolean
widget_entry_draw (WbmWidgetEntry * entry, gboolean do_draw) {
  int rect_x     = entry->x,
      rect_y     = entry->y,
      rect_lines = entry->lines,
      rect_cols  = entry->cols;
  int saved_lines = entry->wb->lines,
      saved_cols  = entry->wb->cols;

  if (entry->with_frame) {
    rect_x++;
    rect_y++;
    rect_lines-=2;
    rect_cols-=2;
  }

  if (do_draw) {
    tty_setcolor (WBLOCK_COLOR_NORMAL);
    if (entry->with_frame) {
      tty_setcolor (WBLOCK_FRAME_COLOR_NORMAL);

      tty_fill_region (
        rect_y,
        rect_x,
        MIN (rect_lines, entry->wb->lines),
        MIN (rect_cols, entry->wb->cols),
        ' '
      );

      tty_draw_box (
        rect_y-1,
        rect_x-1,
        MIN (rect_lines, entry->wb->lines)+2,
        MIN (rect_cols, entry->wb->cols)+2,
        FALSE
      );
    }
    else {
      tty_fill_region (
        rect_y,
        rect_x,
        rect_lines,
        rect_cols,
        ' '
      );
    }
  }
  else {
    entry->wb->y = rect_y;
    entry->wb->x = rect_x;
  }

  WBLOCK_DRAW (
    entry->wb,
    rect_y-entry->offset, /*here block will being drawn*/
    rect_x,             /*here block will being drawn*/
    rect_y,
    rect_x,
    rect_lines,
    rect_cols,
    do_draw);



  return entry->wb->lines<saved_lines || entry->wb->cols<saved_cols;
}

static void
wbm_move_cursor (WBlockMain *wbm) {
  WbmWidgetEntry * entry = wbm->selected_entry;
  if (entry->selected_widget &&
      entry->selected_widget->cursor_y!=-1 &&
      entry->selected_widget->cursor_x!=-1)
  {
    tty_gotoyx (
      entry->selected_widget->y + entry->selected_widget->cursor_y,
      entry->selected_widget->x + entry->selected_widget->cursor_x);
  }
  else {
    tty_gotoyx (LINES,COLS);
  }
}

static gboolean
wbm_wblock_draw (WBlockMain *wbm, gboolean do_draw) {
  gboolean redraw_dialog_stack = FALSE;
  for (GList *l=wbm->widget_entries;l;l=l->next) {
    WbmWidgetEntry * entry = WIDGET_ENTRY (l);
    redraw_dialog_stack |= widget_entry_draw (entry, do_draw);
  }
  wbm_move_cursor (wbm);
  return redraw_dialog_stack;
}



static void
entry_normalize_offset (WbmWidgetEntry *entry) {
  int widget_lines_for_wb = entry->lines + (entry->with_frame ? -2 : 0);
  entry->offset = MIN(MAX(entry->offset,0),MAX(entry->wb->lines - widget_lines_for_wb,0));
}

static void
wbm_normalize_offset (WBlockMain *wbm) {
  for (GList *l=wbm->widget_entries;l;l=l->next) {
    WbmWidgetEntry * entry = WIDGET_ENTRY (l);
    entry_normalize_offset (entry);
  }
}



static gboolean
wbm_entry_mouse (WbmWidgetEntry * entry, mouse_msg_t msg, mouse_event_t * event) {
  WBlock *c = wblock_get_widget_yx (entry->wb, event->y, event->x); //most depth widget
  while (c) {
    if (c->mouse) {
      gboolean res;
      int delta_x = c->x,
          delta_y = c->y;
      event->x -= delta_x;
      event->y -= delta_y;
      res = WBLOCK_MOUSE (c, msg, event);
      event->x += delta_x;
      event->y += delta_y;
      if (res) {
        entry->selected_widget = c;
        return TRUE;
      }
    }
    c = c->parent;
  }
  entry->selected_widget = NULL;
  return FALSE;
}


static void
wbm_erase_redraw_1 (WBlock *wb) {
  wb->redraw = FALSE;
  for (GList *l=wb->widgets;l;l=l->next) {
    wbm_erase_redraw_1 (WBLOCK_DATA (l));
  }
}

static void
entry_erase_redraw (WbmWidgetEntry * entry) {
  wbm_erase_redraw_1 (entry->wb);
}

static void
wbm_erase_redraw (WBlockMain * wbm) {
  for (GList *l=wbm->widget_entries; l; l=l->next) {
    WbmWidgetEntry * entry = WIDGET_ENTRY (l);
    entry_erase_redraw (entry);
  }
}


static void
wbm_redraw_full (WBlockMain *wbm) {
  gboolean redraw_dialog_stack = WBM_UPDATE_COORDS (wbm);
  if (redraw_dialog_stack) {
    dialog_change_screen_size ();
  }
  else {
    WBM_REDRAW (wbm);
  }
  wbm_erase_redraw (wbm);
  wbm_move_cursor (wbm);
}

static void
entry_redraw_full (WbmWidgetEntry * entry) {
  gboolean redraw_dlg = widget_entry_draw (entry, FALSE);
  if (redraw_dlg)
    dialog_change_screen_size ();
  else
    widget_entry_draw (entry, TRUE);
  entry_erase_redraw (entry);
}

static void
entry_update_coord (WbmWidgetEntry * entry) {
  widget_entry_draw (entry, FALSE);
}

static gboolean
entry_redraw (WbmWidgetEntry * entry) {
  return widget_entry_draw (entry, TRUE);
}

static gboolean
wbm_exists_redraw_1 (WBlock *wb) {
  if (wb->redraw)
    return TRUE;
  for (GList *l=wb->widgets;l;l=l->next) {
    if (wbm_exists_redraw_1 (WBLOCK_DATA (l)))
      return TRUE;
  }
  return FALSE;
}


static gboolean
wbm_exists_redraw (WBlockMain * wbm) {
  for (GList *l=wbm->widget_entries; l; l=l->next) {
    WbmWidgetEntry * entry = WIDGET_ENTRY (l);
    if (wbm_exists_redraw_1 (entry->wb))
      return TRUE;
  }
  return FALSE;
}

static WbmWidgetEntry *
wbm_get_entry_yx (WBlockMain *wbm, int y, int x) {
  for (GList *l = g_list_last (wbm->widget_entries); l; l=l->prev) {
    WbmWidgetEntry * entry = WIDGET_ENTRY (l);
    if (IN_RECTANGLE (y, x, entry->y, entry->x, entry->lines, entry->cols))
      return entry;
  }
  return NULL;
}

static void
wbm_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
  WBlockMain *wbm = WBMAIN(w);
  gboolean handled = FALSE;
  int delta_x = w->x,
      delta_y = w->y;
  WbmWidgetEntry * entry = wbm_get_entry_yx (wbm, event->y+delta_y, event->x+delta_x);

  if (!entry) {
    if (msg==MSG_MOUSE_CLICK) {
      WDialog *h = w->owner;
      h->ret_value = B_CANCEL;
      dlg_stop (h);
    }
    return;
  }


  wbm->selected_entry = entry;

  event->y+=delta_y;
  event->x+=delta_x;
  handled = wbm_entry_mouse (entry, msg, event);
  event->y-=delta_y;
  event->x-=delta_x;

  if (!handled) {
    int saved_offset = entry->offset;
    switch (msg) {
      case MSG_MOUSE_SCROLL_UP:
          entry->offset-=2;
          entry_normalize_offset (entry);
          break;
      case MSG_MOUSE_SCROLL_DOWN:
          entry->offset+=2;
          entry_normalize_offset (entry);
          break;
      default:
          break;
    }
    if (saved_offset!=entry->offset)
      entry_update_coord (entry);
      entry_redraw (entry);
  }
  else {
    if (wbm_exists_redraw (wbm))
      wbm_redraw_full (wbm);
  }
}

static void
wbm_recalc_position (WBlockMain *wbm) {
  for (GList *l = wbm->widget_entries; l; l=l->next) {
    WbmWidgetEntry * entry = WIDGET_ENTRY (l);
    entry->calcpos (entry);
  }
}

static cb_ret_t
wbm_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  int command;
  cb_ret_t handled = MSG_NOT_HANDLED;
  WBlockMain *wbm = WBMAIN(w);
  WbmWidgetEntry *entry = wbm->selected_entry;
  int saved_offset = entry->offset;

  (void) sender;
  (void) data;

  switch (msg) {
    case MSG_RESIZE:
    case MSG_INIT:
      wbm_recalc_position (wbm);
      WIDGET (wbm)->x=1;
      WIDGET (wbm)->y=1;
      WIDGET (wbm)->lines=LINES;
      WIDGET (wbm)->cols=COLS;
      WBM_UPDATE_COORDS (wbm);
      wbm_normalize_offset (wbm);
      break;
    case MSG_DRAW:
      WBM_REDRAW (wbm);
      return MSG_HANDLED;
    case MSG_KEY:
      if (entry &&
          entry->selected_widget &&
          entry->selected_widget->key &&
          WBLOCK_KEY (entry->selected_widget, parm))
      {
        if (wbm_exists_redraw (wbm)) {
          wbm_redraw_full (wbm);
          return MSG_HANDLED;
        }
        else {
          return MSG_HANDLED;
        }
      }
      break;
    default:
      break;
  }

  switch (msg) {
    case MSG_KEY:
      command = keybind_lookup_keymap_command (mcgdb_bpw_map, parm);
      switch (command) {
        case CK_Up:
          entry->offset-=1;
          handled=MSG_HANDLED;
          break;
        case CK_Down:
          entry->offset+=1;
          handled=MSG_HANDLED;
          break;
        case CK_PageUp:
          entry->offset-=w->lines/3;
          handled=MSG_HANDLED;
          break;
        case CK_PageDown:
          entry->offset+=w->lines/3;
          handled=MSG_HANDLED;
          break;
        default:
          break;
      }
      entry_normalize_offset (entry);
      if (saved_offset!=entry->offset)
        wbm_redraw_full (entry->wbm);
      break;
    default:
      break;
  }

  return handled;
}


WBlockMain *wblock_main_new (void) {
  WBlockMain *wbm = g_new0 (WBlockMain, 1);
  Widget *w = WIDGET(wbm);
  widget_init (w, 1, 1, LINES, COLS, wbm_callback, wbm_mouse_callback);
  widget_set_options (w, WOP_SELECTABLE, TRUE);
  return wbm;
}




void
wblock_main_save (WBlockMain *wbm) {
  for (GList *l=wbm->widget_entries;l;l=l->next) {
    WbmWidgetEntry * entry = (WbmWidgetEntry *)(l->data);
    wblock_save (entry->wb);
  }
}

void
wblock_main_add_widget (
  WBlockMain *wbm,
  WBlock *wb,
  pos_callback_t calcpos,
  gpointer calcpos_data,
  gboolean with_frame
)
{
  WbmWidgetEntry * entry = g_new0 (WbmWidgetEntry, 1);
  entry->wbm = wbm;

  message_assert (calcpos || calcpos_data);
  wb->entry = entry;
  entry->wb=wb;
  entry->calcpos        = calcpos ? calcpos : default_calcpos;
  entry->calcpos_data   = calcpos_data;
  entry->with_frame     = with_frame;
  wbm->widget_entries   = g_list_append (wbm->widget_entries, entry);

  wbm->selected_entry = entry;
}


void wblock_main_free (WBlockMain * wbm) {
  GList *entries = wbm->widget_entries;

  dlg_destroy (WIDGET(wbm)->owner); /*free (wbm)*/

  for (GList *l=entries;l;l=l->next) {
    WbmWidgetEntry * entry = (WbmWidgetEntry *)(l->data);
    if (entry->calcpos_data)
      calcpos_data_free (entry->calcpos_data);
    wblock_destroy (entry->wb);
    g_free (entry->wb);
  }

  g_list_free_full (entries, g_free);
}


static cb_ret_t
wbm_dlg_default_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data)
{
    WBlockMain *wbm =  WBMAIN (DIALOG (w)->widgets->data);
    return WIDGET (wbm)->callback (WIDGET (wbm), sender, msg, parm, data);
}


int
wblock_main_run (WBlockMain * wbm) {
  WDialog *dlg;
  int return_val;
  dlg = dlg_create (TRUE, 1, 1, LINES, COLS, WPOS_KEEP_DEFAULT, FALSE, NULL, wbm_dlg_default_callback,
                    NULL, "[wblock]", NULL);

  message_assert (wbm->selected_entry!=NULL);

  add_widget (dlg, wbm);
  return_val = dlg_run (dlg);

  wblock_main_save (wbm); //recursive save data

  return return_val;
}




void
default_calcpos (WbmWidgetEntry *entry) {
  CalcposData *data = (CalcposData *)entry->calcpos_data;
  int LINES0 = MAX (0, LINES - 4);
  int y0     = data->y>=0     ? data->y     : 0;
  int x0     = data->x>=0     ? data->x     : 0;
  int lines0 = data->lines>0 ? data->lines : LINES0;
  int cols0  = data->cols>0  ? data->cols  : COLS;
  int add_y  = entry->with_frame ? 2 : 0;
  int add_x  = entry->with_frame ? 2 : 0;

  entry->y     = y0;
  entry->x     = x0;
  entry->lines = lines0;
  entry->cols  = cols0;

  if (data->lines<=0 || data->cols<=0) {
    widget_entry_draw (entry, FALSE); /*recalculate coordinates*/
  }

  if (data->closest_to_y) {
    int len = entry->y + entry->wb->lines + add_y - LINES0;
    if (len > 0) {
      entry->y = MAX (2, entry->y - len);
    }
    entry->lines = MIN (LINES0, entry->wb->lines + add_y);
  }
  else {
    entry->lines = data->lines>0 ? data->lines : MIN (LINES0 - entry->y, entry->wb->lines + add_y);
  }

  entry->cols  = data->cols>0  ? data->cols  : MIN (COLS  - entry->x, entry->wb->cols  + add_x);
  entry_update_coord (entry);
}

CalcposData *
calcpos_data_new () {
  CalcposData *calcpos_data = g_new0 (CalcposData, 1);
  return calcpos_data;
}

void calcpos_data_free (CalcposData *calcpos_data) {
  g_free (calcpos_data);
}






