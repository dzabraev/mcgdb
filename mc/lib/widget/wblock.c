#include <config.h>

#include "lib/global.h"
#include <strings.h>
#include "src/keybind-defaults.h" /*bpw_map*/
#include "src/mcgdb.h"
#include "lib/widget/wblock.h"
#include "lib/skin.h" /*EDITOR_NORMAL_COLOR*/
#include "lib/tty/tty.h"

#define WBMAIN(w) ((WBlockMain *)(w))




#define WBM_UPDATE_COORDS(wbm) wbm_wblock_draw(wbm,FALSE)

#define WBM_REDRAW(wbm) wbm_wblock_draw (wbm,TRUE);



static void
wbm_wblock_draw (WBlockMain *wbm, gboolean do_draw) {
  int rect_x = WIDGET(wbm)->x,
      rect_y = WIDGET(wbm)->y,
      rect_lines = WIDGET(wbm)->lines,
      rect_cols  = WIDGET(wbm)->cols;

  if (wbm->with_frame) {
    rect_x++;
    rect_y++;
    rect_lines-=2;
    rect_cols-=2;
  }

  if (do_draw) {
    tty_setcolor (WBLOCK_COLOR_NORMAL);
    if (wbm->with_frame) {
      tty_setcolor (WBLOCK_FRAME_COLOR_NORMAL);

      tty_fill_region (
        rect_y,
        rect_x,
        MIN (rect_lines, wbm->wb->lines),
        MIN (rect_cols, wbm->wb->cols),
        ' '
      );

      tty_draw_box (
        rect_y-1,
        rect_x-1,
        MIN (rect_lines, wbm->wb->lines)+2,
        MIN (rect_cols, wbm->wb->cols)+2,
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

  WBLOCK_DRAW (
    wbm->wb,
    rect_y-wbm->offset, /*here block will being drawn*/
    rect_x,             /*here block will being drawn*/
    rect_y,
    rect_x,
    rect_lines,
    rect_cols,
    do_draw);


  if (wbm->selected_widget && wbm->selected_widget->cursor_y!=-1 && wbm->selected_widget->cursor_x!=-1) {
    tty_gotoyx (
      wbm->selected_widget->y + wbm->selected_widget->cursor_y,
      wbm->selected_widget->x + wbm->selected_widget->cursor_x);
  }
  else {
    tty_gotoyx (LINES,COLS);
  }
}

static WBlockMain * wbm_new (WBlock *wb, pos_callback_t calcpos, gpointer data, gboolean with_frame);
static void wbm_cleanup (WBlockMain * wbm);
static gboolean wbm_exists_redraw (WBlockMain * wbm);


static void
wbm_normalize_offset (WBlockMain *wbm) {
  int widget_lines_for_wb = WIDGET(wbm)->lines + (wbm->with_frame ? -2 : 0);
  wbm->offset = MIN(MAX(wbm->offset,0),MAX(wbm->wb->lines - widget_lines_for_wb,0));
}

static gboolean
wbm_mouse (WBlockMain *wbm, mouse_msg_t msg, mouse_event_t * event) {
  WBlock *c = wblock_get_widget_yx (wbm->wb, event->y, event->x); //most depth widget
  while (c) {
    if (c->mouse) {
      gboolean res;
      event->x-=c->x;
      event->y-=c->y;
      res = WBLOCK_MOUSE (c, msg, event);
      event->x+=c->x;
      event->y+=c->y;
      if (res) {
        wbm->selected_widget = c;
        return TRUE;
      }
    }
    c = c->parent;
  }
  wbm->selected_widget = NULL;
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
wbm_erase_redraw (WBlockMain * wbm) {
  WBlock *wb = wbm->wb;
  return wbm_erase_redraw_1 (wb);
}

static void
wbm_redraw_full (WBlockMain *wbm) {
  int saved_lines = wbm->wb->lines;
  WBM_UPDATE_COORDS (wbm);
  if (saved_lines>wbm->wb->lines) {
    /*redraw all dialogs*/
    dialog_change_screen_size ();
  }
  else {
    WBM_REDRAW (wbm);
  }
  wbm_erase_redraw (wbm);
}

static gboolean
wbm_exists_redraw_1 (WBlock *wb) {
  if (wb->redraw)
    return TRUE;
  for (GList *l=wb->widgets;l;l=l->next) {
    if (wbm_exists_redraw_1 ( WBLOCK_DATA (l)))
      return TRUE;
  }
  return FALSE;
}

static gboolean
wbm_exists_redraw (WBlockMain * wbm) {
  WBlock *wb = wbm->wb;
  return wbm_exists_redraw_1 (wb);
}





static void
wbm_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event) {
  WBlockMain *wbm = WBMAIN(w);
  int saved_offset = wbm->offset;
  int y_saved=w->y, x_saved=w->x;
  gboolean res, redraw;
  event->y+=y_saved;
  event->x+=x_saved;
  res = wbm_mouse (wbm, msg, event);
  event->y-=y_saved;
  event->x-=x_saved;
  if (wbm_exists_redraw (wbm))
    goto label_redraw;
  else if (res)
    return;

  switch (msg) {
    case MSG_MOUSE_SCROLL_UP:
        wbm->offset-=2;
        wbm_normalize_offset (wbm);
        break;
    case MSG_MOUSE_SCROLL_DOWN:
        wbm->offset+=2;
        wbm_normalize_offset (wbm);
        break;
    default:
        break;
  }

  redraw = saved_offset!=wbm->offset;
  if (redraw) {
    label_redraw: wbm_redraw_full (wbm);
  }
}

static cb_ret_t
wbm_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data) {
  int command;
  gboolean redraw;
  cb_ret_t handled = MSG_NOT_HANDLED;
  WBlockMain *wbm = WBMAIN(w);
  int saved_offset = wbm->offset;

  (void) sender;
  (void) data;

  switch (msg) {
    case MSG_RESIZE:
    case MSG_INIT:
      {
        wbm->calcpos(wbm);
      }
      WBM_UPDATE_COORDS (wbm);
      wbm_normalize_offset (wbm);
      break;
    case MSG_DRAW:
      WBM_REDRAW (wbm);
      return MSG_HANDLED;
    case MSG_KEY:
      if (wbm->selected_widget &&
          wbm->selected_widget->key &&
          WBLOCK_KEY (wbm->selected_widget, parm))
      {
        if (wbm->selected_widget->redraw) {
          wbm->selected_widget->redraw = FALSE;
          handled = MSG_HANDLED;
          goto label_redraw;
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
          wbm->offset-=1;
          handled=MSG_HANDLED;
          break;
        case CK_Down:
          wbm->offset+=1;
          handled=MSG_HANDLED;
          break;
        case CK_PageUp:
          wbm->offset-=w->lines/3;
          handled=MSG_HANDLED;
          break;
        case CK_PageDown:
          wbm->offset+=w->lines/3;
          handled=MSG_HANDLED;
          break;
        default:
          break;
      }
      wbm_normalize_offset (wbm);
      redraw = saved_offset!=wbm->offset;
      if (redraw) {
        label_redraw: wbm_redraw_full (wbm);
      }
      break;
    default:
      break;
  }

  return handled;
}

static WBlockMain *
wbm_new (WBlock *wb, pos_callback_t calcpos, gpointer calcpos_data, gboolean with_frame) {
  WBlockMain *wbm = g_new0 (WBlockMain, 1);
  Widget *w;

  wbm->wb = wb;
  wbm->calcpos = calcpos ? calcpos : default_calcpos_data;
  message_assert (calcpos || calcpos_data);
  wbm->calcpos_data = calcpos_data;
  wbm->with_frame = with_frame;
  w = WIDGET(wbm);
  widget_init (w, 1, 1, 1, 1, wbm_callback, wbm_mouse_callback);
  widget_set_options (w, WOP_SELECTABLE, TRUE);
  return wbm;
}

static void
wbm_cleanup (WBlockMain * wbm) {
  (void) wbm;
}

WBlock *
wblock_get_widget_yx (WBlock *wb, int y, int x) {
  if (!YX_IN_WIDGET (wb,y,x))
    return NULL;

  for (GList *l=g_list_last (wb->widgets);l;l=l->prev) {
    WBlock *c = WBLOCK (l->data);
    if (YX_IN_WIDGET (c,y,x)) {
      return wblock_get_widget_yx (c, y, x);
    }
  }

  return wb;
}

void
wblock_shift_yx (WBlock *wb, int shift_y, int shift_x) {
  wb->y += shift_y;
  wb->x += shift_x;
  for (GList *l=wb->widgets;l;l=l->next) {
    wblock_shift_yx (WBLOCK_DATA (l), shift_y, shift_x);
  }
}

void
wblock_dfl_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  /* From point (y0,x0) widget will be drawing. Rectangle y,x,lines,cols is area in which block will
      will be drawing. Only points of block which intersect with rectangle will draw.
  */
  int y_line_max=y0,
      x_line_max=x0;
  int y_widget=y0, x_widget=x0;

  for (GList *l=wb->widgets;l;l=l->next) {
    WBlock *c = WBLOCK (l->data);

    if (!do_draw) {
      if (c->style.layout==LAYOUT_BLOCK) {
        y_widget = y_line_max;
        x_widget = x0;
      }

      x_widget+=c->style.margin.left;
      y_widget+=c->style.margin.top;

      c->y = y_widget;
      c->x = x_widget;
      c->lines=-1;
      c->cols=-1;
    }
    else {
      tty_setcolor (WBLOCK_COLOR_NORMAL);
    }

    WBLOCK_DRAW (c, c->y, c->x, y, x, lines, cols, do_draw);

    if (!do_draw) {
      message_assert (c->lines>=0);
      message_assert (c->cols>=0);
      switch (c->style.width_type) {
        case WIDTH_MAX:
          c->cols = MAX (c->cols, x + cols - x_widget - c->style.margin.right);
          break;
        default:
          break;
      }
      /*do align*/
      {
        int xc1,xc2,shift;
        switch (c->style.align) {
          case ALIGN_CENTER:
            xc1 = (x_widget + x+cols-1)/2; /*center of available space*/
            xc2 = x_widget + c->cols/2; /*center of widget*/
            shift = xc1 - xc2;
            wblock_shift_yx (c, 0, shift);
            break;
          case ALIGN_RIGHT:
            break;
          default:
            break;
        }
      }

      y_line_max = MAX(y_line_max, y_widget+c->lines+c->style.margin.bottom);
      x_line_max = MAX(x_line_max, x_widget+c->cols+c->style.margin.right);

      if (c->style.layout==LAYOUT_BLOCK) {
        y_widget = y_line_max;
        x_widget = x0;
      }
      else if (c->style.layout==LAYOUT_INLINE) {
        x_widget+=c->cols+c->style.margin.right;
      }
    }
  }

  if (!do_draw) {
    wb->x = x0;
    wb->y = y0;
    wb->lines = y_line_max - y0;
    wb->cols = x_line_max - x0;
  }
}


void
wblock_dfl_destroy (WBlock *wb) {
  for (GList *l=wb->widgets;l!=NULL;l=l->next) {
    WBLOCK_DESTROY (WBLOCK (l->data));
  }
  g_list_free (wb->widgets);
  g_free (wb->wdata);
}

void
wblock_init (
  WBlock *wb,
  wblock_mouse_cb_t   mouse,
  wblock_key_cb_t     key,
  wblock_destroy_cb_t destroy,
  wblock_draw_cb_t    draw,
  wblock_save_cb_t    save,
  gpointer wdata)
{
  bzero (wb, sizeof (WBlock));
  wb->destroy   = destroy   ? destroy   : wblock_dfl_destroy;
  wb->draw      = draw      ? draw      : wblock_dfl_draw;
  wb->key       = key;
  wb->mouse     = mouse;
  wb->save      = save;
  wb->wdata     = wdata;
  wb->cursor_y = -1;
  wb->cursor_x = -1;
}

WBlock *
wblock_new (
  wblock_mouse_cb_t   mouse,
  wblock_key_cb_t     key,
  wblock_destroy_cb_t destroy,
  wblock_draw_cb_t    draw,
  wblock_save_cb_t    save,
  gpointer wdata)
{
  WBlock *wb = g_new0 (WBlock,1);
  wblock_init (wb, mouse, key, destroy, draw, save, wdata);
  return wb;
}


void
wblock_add_widget (WBlock * wb, WBlock * widget) {
  wb->widgets = g_list_append (wb->widgets, widget);
  widget->parent = wb;
}

void
draw_string (const char *p, int *draw_lines, int *draw_cols, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw, gboolean oneline) {
  int x_line=x0;
  int x_line_max=x0;
  int y_line=y0;
  if (p) {
    while (*p) {
      if (!do_draw || IN_RECTANGLE (y_line,x_line,y,x,lines,cols)) {
        if (do_draw) {
          tty_gotoyx (y_line, x_line);
          tty_print_char (*p);
        }
        x_line++;
      }
      if (!oneline && x_line>=x+cols) {
        x_line_max = MAX (x_line, x_line_max);
        x_line = x0;
        y_line ++;
      }
      p++;
    }
  }


  x_line_max = MAX (x_line, x_line_max);
  *draw_cols += x_line_max - x0;
  if (x_line>x0)
    y_line++;
  *draw_lines += y_line - y0;
}


void
draw_string_oneline (const char *p, int *draw_cols, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  int draw_lines=0;
  draw_string (p,&draw_lines,draw_cols,y0,x0,y,x,lines,cols,do_draw,TRUE);
}

static cb_ret_t
wblock_dlg_default_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data)
{
    WBlockMain *wbm =  WBMAIN (DIALOG (w)->widgets->data);
    return WIDGET (wbm)->callback (WIDGET (wbm), sender, msg, parm, data);
}


WBlockMain *
wblock_get_wbm (WBlock *wb) {
  WBlock *p = wb->parent, *q=wb;
  while (p) {
    q=p;
    p=p->parent;
  }
  return q->wbm;
}

WDialog *
wblock_get_dialog (WBlock *wb) {
  return WIDGET (wblock_get_wbm (wb))->owner;
}


WBlock *
set_layout (WBlock *wb, layout_t layout) {
  wb->style.layout = layout;
  return wb;
}

WBlock *
layout_inline (WBlock *wb) {
  return set_layout (wb,LAYOUT_INLINE);
}

WBlock *
wblock_width_auto (WBlock *wb) {
  wb->style.width_type = WIDTH_AUTO;
  return wb;
}


WBlock *
wblock_empty (void) {
  return wblock_new(NULL,NULL,NULL,NULL,NULL,NULL);
}

WBlock *
set_margin (WBlock *wb, int left, int top, int right, int bottom) {
  wb->style.margin.left     =left;
  wb->style.margin.top      =top;
  wb->style.margin.right    =right;
  wb->style.margin.bottom   =bottom;
  return wb;
}

WBlock *
wblock_newline (void) {
  return set_margin (wblock_empty (), 0, 1, 0, 0);
}

WBlock *
wblock_nspace (int n) {
  return set_margin (
          layout_inline (
            wblock_empty ()), n, 0, 0, 0);
}

void
wblock_save (WBlock *wb) {
  if (wb->save)
    WBLOCK_SAVE (wb);
  for (GList *l=wb->widgets;l;l=l->next) {
    wblock_save (l->data);
  }
}


int
wblock_run (WBlock * wb, pos_callback_t calcpos, gpointer calcpos_data) {
  WDialog *dlg;
  WBlockMain * wbm = wbm_new (wb, calcpos, calcpos_data, TRUE);
  int return_val;
  dlg = dlg_create (TRUE, 0, 0, 0, 0, WPOS_KEEP_DEFAULT, FALSE, NULL, wblock_dlg_default_callback,
                    NULL, "[wblock]", NULL);

  wb->wbm = wbm;
  add_widget (dlg, wbm);
  return_val = dlg_run (dlg);

  wblock_save (wb); /*recursive save data*/

  wbm_cleanup (wbm);
  dlg_destroy (dlg);


  return return_val;
}


int
get_utf (const gchar * str, int *char_length)
{
    gunichar res;
    gunichar ch;
    gchar *next_ch = NULL;

    res = g_utf8_get_char_validated (str, -1);
    if (res == (gunichar) (-2) || res == (gunichar) (-1))
    {
        /* Retry with explicit bytes to make sure it's not a buffer boundary */
        size_t i;
        gchar utf8_buf[UTF8_CHAR_LEN + 1];

        for (i = 0; i < UTF8_CHAR_LEN; i++)
            utf8_buf[i] = str [i];
        utf8_buf[i] = '\0';
        res = g_utf8_get_char_validated (utf8_buf, -1);
    }

    if (res == (gunichar) (-2) || res == (gunichar) (-1))
    {
        ch = *str;
        *char_length = 0;
    }
    else
    {
        ch = res;
        /* Calculate UTF-8 char length */
        next_ch = g_utf8_next_char (str);
        *char_length = next_ch - str;
    }

    return (int) ch;
}

WBlock *
wblock_empty_new (void) {
  return wblock_new (NULL,NULL,NULL,NULL,NULL,NULL);
}

void
default_calcpos_data (WBlockMain *wbm) {
  Widget *w = WIDGET (wbm);
  CalcposData *data = (CalcposData *)wbm->calcpos_data;
  int LINES0 = LINES - 4;
  int y0     = data->y>0     ? data->y     : 1;
  int x0     = data->x>0     ? data->x     : 1;
  int lines0 = data->lines>0 ? data->lines : LINES0;
  int cols0  = data->cols>0  ? data->cols  : COLS;
  int add_y  = wbm->with_frame ? 2 : 0;
  int add_x  = wbm->with_frame ? 2 : 0;

  w->y     = y0;
  w->x     = x0;
  w->lines = lines0;
  w->cols  = cols0;

  if (data->lines<=0 || data->cols<=0) {
    wbm_wblock_draw (wbm, FALSE); /*recalculate coordinates*/
  }

  if (data->closest_to_y) {
    int len = w->y + wbm->wb->lines + add_y - LINES0;
    if (len > 0) {
      w->y = MAX (2, w->y - len);
    }
    w->lines = MIN (LINES0, wbm->wb->lines + add_y);
  }
  else {
    w->lines = data->lines>0 ? data->lines : MIN (LINES0 - w->y, wbm->wb->lines + add_y);
  }

  w->cols  = data->cols>0  ? data->cols  : MIN (COLS  - w->x, wbm->wb->cols  + add_x);

}

CalcposData *
calcpos_data_new () {
  CalcposData *calcpos_data = g_new0 (CalcposData, 1);
  return calcpos_data;
}

void calcpos_data_free (CalcposData *calcpos_data) {
  g_free (calcpos_data);
}




void wblock_set_mouse (WBlock *wb, wblock_mouse_cb_t mouse) {
  wb->mouse = mouse;
}

void wblock_set_key (WBlock *wb, wblock_key_cb_t key) {
  wb->key = key;
}

void wblock_set_destroy (WBlock *wb, wblock_destroy_cb_t destroy) {
  wb->destroy = destroy;
}

void wblock_set_draw (WBlock *wb, wblock_draw_cb_t draw) {
  wb->draw = draw;
}

void wblock_set_save (WBlock *wb, wblock_save_cb_t save) {
  wb->save = save;
}

void wblock_set_wdata (WBlock *wb, gpointer wdata) {
  wb->wdata = wdata;
}

