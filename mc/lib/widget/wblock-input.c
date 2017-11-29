#include <config.h>
#include "lib/global.h"
#include "lib/tty/tty.h"

//#include "src/editor/editbuffer.h"
#include "src/keybind-defaults.h"

#include "wblock.h"
#include "src/mcgdb.h"


static void
buf_insert_lines (GArray *buf, gchar *lines, int y) {
  char *p = lines;
  GArray *row = g_array_new (FALSE, FALSE, sizeof (gunichar));
  if (y==-1)
    y=buf->len;
  while (p && p[0]) {
    if (*p=='\n') {
      if (y>=(int)buf->len)
        g_array_append_val (buf, row);
      else
        g_array_insert_val (buf, y, row);
      y++;
      p++;
    }
    else {
      gunichar ch = g_utf8_get_char (p);
      g_array_append_val (row, ch);
      p = g_utf8_next_char (p);
    }
  }
  if (y>=(int)buf->len)
    g_array_append_val (buf, row);
  else
    g_array_insert_val (buf, y, row);
}

static void
buf_append_lines (GArray *buf, gchar *lines) {
  buf_insert_lines (buf, lines, -1);
}

static void
buf_to_string (GArray *buf, gchar **string) {
  GArray *row = g_array_index (buf,GArray *, 0);
  g_free (string[0]);
  string[0] = buf->len > 0 ? g_ucs4_to_utf8 (
    (gunichar *) row->data, row->len, NULL, NULL, NULL) : NULL;
  for (int idx=1,size=buf->len;idx<size;idx++) {
    char *new_str;
    row = g_array_index (buf,GArray *, idx);
    new_str = g_strdup_printf ( "%s %s", string[0],
          g_ucs4_to_utf8 (
            (gunichar *) row->data, row->len, NULL, NULL, NULL));
    g_free (string[0]);
    string[0] = new_str;
  }
}


static GArray *
buf_get_line (GArray *buf, int y) {
  return g_array_index (buf, GArray *, y);
}

static GArray *
wblock_input_get_line (WBlock *wb, int y) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  return buf_get_line (data->buf, y);
}


static GArray *
wblock_input_current_line (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  int pos_y = data->offset_y + wb->cursor_y;
  return g_array_index (data->buf, GArray *, pos_y);
}

static void
wblock_input_decr_lines (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  wb->lines = MAX (wb->lines-1, data->h_min);
}

static void
wblock_input_incr_lines (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  wb->lines = MIN (wb->lines+1, data->h_max);
}


static void
wblock_input_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  if (!do_draw) {
    wb->y=y0;
    wb->x=x0;
    wb->cols = cols;
    wb->lines = MIN (lines, MAX (data->h_min, MIN (data->h_max, (int)data->buf->len)));
  }
  else {
    tty_setcolor (WBLOCK_INPUT_COLOR);
    tty_fill_region (wb->y,wb->x,wb->lines,wb->cols,' ');
    for (int line_idx=0; line_idx < MIN(wb->lines,(int)data->buf->len); line_idx++) {
      GArray *row = buf_get_line (data->buf, data->offset_y + line_idx);
      for (int col_idx=0; col_idx < MIN (wb->cols,(int)row->len); col_idx++) {
        gunichar ch = g_array_index (row, gunichar, data->offset_x+col_idx);
        int draw_x = x0+col_idx,
            draw_y = y0+line_idx;
        if (IN_RECTANGLE (draw_y, draw_x, y, x, lines, cols)) {
          tty_gotoyx (draw_y, draw_x);
          tty_print_anychar (g_unichar_isprint (ch) ? ch : '.');
        }
      }
    }
    /* blinkable cursor will be setup in WBM_WBLOCK_DRAW */
  }
}

static gboolean
wblock_input_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  if (msg==MSG_MOUSE_CLICK) {
    int len;
    wb->cursor_y = event->y+data->offset_y < (int)data->buf->len ?
                    event->y : (int)data->buf->len - 1 - data->offset_y;

    len = (int)wblock_input_current_line (wb)->len;
    wb->cursor_x = data->offset_x+event->x < len ?
                      event->x : len-data->offset_x;

    wb->redraw = TRUE;
    return TRUE;
  }
  else {
    return FALSE;
  }
}


static void
wblock_input_view_toleft (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  data->offset_x=0;
  wb->cursor_x=0;
  wb->redraw=TRUE;
}

static void
wblock_input_view_toright (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  int len = wblock_input_current_line (wb)->len;
  data->offset_x = MAX (0, len - wb->cols);
  wb->cursor_x = len - data->offset_x;
  wb->redraw=TRUE;
}

static void
wblock_input_decr_cursor_x (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  if (wb->cursor_x>0) {
    wb->cursor_x--;
    wb->redraw=TRUE;
  }
  else {
    if (data->offset_x>0) {
      data->offset_x--;
      wb->redraw=TRUE;
    }
    else if (wb->cursor_y>0 || data->offset_y>0) {
      if (wb->cursor_y>0) {
        wb->cursor_y--;
      }
      else if (data->offset_y>0) {
        data->offset_y--;
      }
      wblock_input_view_toright (wb);
      wb->redraw=TRUE;
    }
  }
}

static void
wblock_input_incr_cursor_x (WBlock *wb) {
  GArray *cur = wblock_input_current_line (wb);
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  if (wb->cursor_x+data->offset_x < (int)cur->len) {
    if (wb->cursor_x < wb->cols)
      wb->cursor_x++;
    else
      data->offset_x++;
    wb->redraw=TRUE;
  }
  else {
    int inc_curs = wb->cursor_y<wb->lines-1,
        inc_off = data->offset_y < (int)data->buf->len - wb->lines - 1;
    if (data->offset_x < (int)cur->len - wb->lines-1) {
      data->offset_x++;
      wb->redraw=TRUE;
    }
    else if (inc_curs || inc_off) {
      if (inc_curs) {
        wb->cursor_y++;
        wb->redraw=TRUE;
      }
      else if (inc_off) {
        data->offset_y++;
        wb->redraw=TRUE;
      }
      data->offset_x = 0;
      wb->cursor_x = 0;
    }
  }
}



static void
wblock_input_move_cursor_y (WBlock *wb, int offset) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  GArray *row;
  int add_cursor = offset > 0 ? MIN (offset, wb->lines - wb->cursor_y - 1) : MAX (offset, - wb->cursor_y);
  int r = offset - add_cursor;
  int add_offset = r > 0 ? MIN (r, (int)data->buf->len - wb->lines - data->offset_y) : MAX (r, -data->offset_y);
  int len;

  data->offset_y+=add_offset;
  wb->cursor_y+=add_cursor;

  wb->redraw = wb->redraw || add_cursor!=0 || add_offset!=0;

  message_assert (data->offset_y>=0 && wb->cursor_y>=0);
  row = wblock_input_current_line (wb);
  len = (int)row->len;
  if (data->offset_x > len) {
    wblock_input_view_toright (wb);
  }
  else if (data->offset_x + wb->cursor_x > len) {
    wb->cursor_x = len - data->offset_x;
  }
}


static void
wblock_input_backspace (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  int pos_y = data->offset_y+wb->cursor_y;
  int pos_x=data->offset_x+wb->cursor_x;
  if ( pos_x > 0) {
    g_array_remove_index (buf_get_line (data->buf, pos_y), pos_x-1);
    if (wb->cursor_x>0)
      wb->cursor_x--;
    else {
      data->offset_x--;
    }
    wb->redraw=TRUE;
  }
  else if (pos_y>0) {
    /*change current line*/
    GArray *row = wblock_input_get_line (wb, pos_y);
    gboolean last_row = pos_y==(int)data->buf->len-1;
    wblock_input_decr_cursor_x (wb);
    g_array_append_vals (
      wblock_input_get_line (wb, pos_y-1),
      row->data,
      row->len
    );
    g_array_remove_index (data->buf,pos_y);
    if (last_row) {
      if (data->offset_y>0) {
        data->offset_y--;
        wb->cursor_y++;
      }
      else {
        wblock_input_decr_lines (wb);
      }
    }
    wb->redraw=TRUE;
  }
}


static void
wblock_input_delete_char (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  size_t pos_x0=data->offset_x+wb->cursor_x,
         pos_y0=data->offset_y+wb->cursor_y,
         pos_x1,
         pos_y1;
  wblock_input_incr_cursor_x (wb);
  pos_x1 = data->offset_x+wb->cursor_x;
  pos_y1 = data->offset_y+wb->cursor_y;
  if (pos_x0!=pos_x1 || pos_y0!=pos_y1) {
    wblock_input_backspace (wb);
    wb->redraw=TRUE;
  }
}

static void
wblock_input_enter (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  size_t pos_y = data->offset_y + wb->cursor_y;
  size_t pos_x = wb->cursor_x + data->offset_x;
  GArray *row = wblock_input_current_line (wb);
  GArray *new_row = g_array_new (FALSE, FALSE, sizeof (gunichar));
  gunichar *insert_data  = row->len>pos_x ? ((gunichar *)row->data) + pos_x : NULL;
  size_t insert_data_len = row->len>pos_x ? row->len - pos_x                : 0;

  if (data->buf->len<=pos_y+1) {
    g_array_append_val (data->buf, new_row);
  }
  else {
    g_array_insert_val (data->buf, pos_y+1, new_row);
  }

  g_array_append_vals (new_row, insert_data, insert_data_len);

  wblock_input_incr_lines (wb);
  g_array_remove_range (row, pos_x, insert_data_len); /*remove copied data*/
  wb->cursor_x = 0;
  data->offset_x = 0;
  wblock_input_move_cursor_y (wb, 1);
  wb->redraw=TRUE;
}


static void
wblock_input_insert_char (WBlock *wb, gunichar parm) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  g_array_insert_val (
    wblock_input_current_line (wb),
    data->offset_x + wb->cursor_x,
    parm);
  wblock_input_incr_cursor_x (wb);
  wb->redraw=TRUE;
}


static gboolean
wait_ucs4 (gchar unit, gunichar *ch) {
  static int len;
  static gchar ubuf[6];
  gunichar *uch;

  ubuf[len++] = unit;

  for (int i=0;i<len;i++) {
    if (g_utf8_validate (ubuf+i, len-i, NULL)) {
      uch = g_utf8_to_ucs4_fast (ubuf+i, len-i, NULL);
      ch[0] = uch[0];
      g_free (uch);
      len=0;
      return TRUE;
    }
  }

  if (len==6) {
    for(int i=0;i<5;i++) {
      ubuf[i] = ubuf[i+1];
    }
    len--;
  }

  return FALSE;
}


static gboolean
wblock_input_key (WBlock *wb, int parm) {
  int command = keybind_lookup_keymap_command (wblock_input_map, parm);

  if (command == CK_IgnoreKey)
    command = CK_InsertChar;

  switch (command) {
    case CK_Enter:
      wblock_input_enter (wb);
      break;
    case CK_Up:
      wblock_input_move_cursor_y (wb, -1);
      break;
    case CK_Down:
      wblock_input_move_cursor_y (wb, 1);
      break;
    case CK_PageUp:
      wblock_input_move_cursor_y (wb, -wb->lines);
      break;
    case CK_PageDown:
      wblock_input_move_cursor_y (wb, wb->lines);
      break;
    case CK_Left:
      wblock_input_decr_cursor_x (wb);
      break;
    case CK_Right:
      wblock_input_incr_cursor_x (wb);
      break;
    case CK_Home:
      wblock_input_view_toleft (wb);
      break;
    case CK_End:
      wblock_input_view_toright (wb);
      break;
    case CK_BackSpace:
      wblock_input_backspace (wb);
      break;
    case CK_InsertChar:
      {
        gunichar ucs4_char;
        gboolean done = wait_ucs4 (parm, &ucs4_char);
        if (done)
          wblock_input_insert_char (wb, ucs4_char);
      }
      break;
    case CK_Delete:
      wblock_input_delete_char (wb);
      break;
    case CK_Cancel:
    default:
      return FALSE;
  }
  return TRUE;
}

static void
wblock_input_save (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  buf_to_string (data->buf, data->result);
}

static void
wblock_input_destroy (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  GArray *buf = data->buf;
  for (int idx=0,size=buf->len;idx<size;idx++) {
    g_array_free (g_array_index (buf,GArray *, idx), TRUE);
  }
  g_array_free (buf, TRUE);
  wblock_dfl_destroy (wb);
}


WBlock *
wblock_input_new (char **initial, int h_min, int h_max) {
  WBlock *wb = g_new0 (WBlock, 1);
  WBlockInputData *data = g_new0 (WBlockInputData, 1);
  data->buf = g_array_new (FALSE, FALSE, sizeof (GArray *));
  data->result = initial;
  data->h_min = h_min;
  data->h_max = h_max;
  buf_append_lines (data->buf, initial[0]);
  g_free (initial[0]);
  wblock_init (wb,
    wblock_input_mouse,
    wblock_input_key,
    wblock_input_destroy,
    wblock_input_draw,
    wblock_input_save,
    data);
  return wb;
}
