#include <config.h>
#include "lib/global.h"
#include "lib/tty/tty.h"

//#include "src/editor/editbuffer.h"
#include "src/keybind-defaults.h"

#include "wblock.h"
#include "src/mcgdb.h"


static void
buf_insert_lines (GArray *buf, char *lines, int y) {
  char *line = lines;
  if (y==-1)
    y=buf->len;
  while (line) {
    int len;
    GArray *new_line = g_array_new (FALSE, FALSE, sizeof (int));
    char *next_line = strchr (line, '\n');
    len = next_line ? (int)(next_line - line) : (int)strlen (line);
    g_array_append_vals (new_line, line, len);
    if (y>=(int)buf->len)
      g_array_append_val (buf, new_line);
    else
      g_array_insert_val (buf, y, new_line);
    y++;

    line = next_line;
    if (line)
      line++; //skip \n
    else
      break;
  }
}

static void
buf_append_lines (GArray *buf, char *lines) {
  buf_insert_lines (buf, lines, -1);
}

static void
buf_to_string (GArray *buf, char **string) {
  g_free (string[0]);
  string[0] = buf->len > 0 ? g_strdup (g_array_index (buf,GArray *, 0)->data) : NULL;
  for (int idx=1,size=buf->len;idx<size;idx++) {
    char *new_str = g_strdup_printf ("%s %s", string[0], g_array_index (buf,GArray *, idx)->data);
    g_free (string[0]);
    string[0] = new_str;
  }
}


static GArray *
buf_get_line (GArray *buf, int y) {
  return g_array_index (buf, GArray *, y);
}



static GArray *
wblock_input_current_line (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  int pos_y = data->offset_y + wb->cursor_y;
  return g_array_index (data->buf, GArray *, pos_y);
}


static void
wblock_input_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  (void) y0;
  (void) x0;
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
        int ch = g_array_index (row, int, data->offset_x+col_idx);
        int draw_x = wb->x+col_idx,
            draw_y = wb->y+line_idx;
        if (IN_RECTANGLE (draw_y, draw_x, y, x, lines, cols)) {
          tty_gotoyx (draw_y, draw_x);
          tty_print_anychar (g_unichar_isprint (ch) ? ch : '.');
        }
      }
    }
    /* blinkable cursor will setup in WBM_WBLOCK_DRAW */
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
    return TRUE;
  }
  else {
    return FALSE;
  }
}

static void
wblock_input_view_toright (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  int len = wblock_input_current_line (wb)->len;
  data->offset_x = len - wb->cols;
  wb->cursor_x = wb->cols-1;
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
        wb->redraw=TRUE;
      }
      else if (data->offset_y>0) {
        data->offset_y--;
        wb->redraw=TRUE;
      }
      wblock_input_view_toright (wb);
    }
  }
}

static void
wblock_input_incr_cursor_x (WBlock *wb) {
  GArray *cur = wblock_input_current_line (wb);
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  if (wb->cursor_x<wb->cols-1) {
    wb->cursor_x++;
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
  int pos_x = wb->cursor_x + data->offset_x;
  int pos_y;
  GArray *row;
  int add_cursor = offset > 0 ? MIN (offset, wb->lines - wb->cursor_y) : MAX (offset, - wb->cursor_y);
  int r = offset - add_cursor;
  int add_offset = r > 0 ? MIN (r, (int)data->buf->len - wb->lines - data->offset_y) : MAX (r, -data->offset_y);

  data->offset_y+=add_offset;
  wb->cursor_y+=add_cursor;

  wb->redraw = wb->redraw || add_cursor!=0 || add_offset!=0;

  pos_y = data->offset_y + wb->cursor_y;

  message_assert (data->offset_y>=0 && wb->cursor_y>=0);

  row = buf_get_line (data->buf, pos_y);
  if ((int)row->len < pos_x) {
    data->offset_x = MAX (0,(int)row->len - wb->cols);
    wb->cursor_x = wb->lines - 1;
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
    GArray *curline = wblock_input_current_line (wb);
    if (wb->cursor_y>0)
      wb->cursor_y--;
    else
      data->offset_y--;
    g_array_remove_index (curline, curline->len-1);
    wblock_input_view_toright (wb); /*move view to right*/
  }
}


static gboolean
wblock_input_key (WBlock *wb, int parm) {
  int command = keybind_lookup_keymap_command (editor_map, parm);
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  GArray *buf = data->buf;

  if (command == CK_IgnoreKey)
    command = CK_InsertChar;

  switch (command) {
    case CK_Enter:
      {
        int pos_y = data->offset_y + wb->cursor_y;
        int pos_x = wb->cursor_x + data->offset_x;
        GArray *row = wblock_input_current_line (wb);
        char *insert_data = (int)row->len>pos_x ? ((char *)row->data) + pos_x : strdup("");
        buf_insert_lines (buf, insert_data, pos_y+1); /*create new row*/
        g_array_remove_range (row, pos_x, buf->len-pos_x); /*remove copied data*/
        wb->cursor_x = 0;
        data->offset_x = 0;
        wblock_input_move_cursor_y (wb, 1);
        wb->redraw=TRUE;
      }
      break;
    case CK_Up:
      wblock_input_move_cursor_y (wb, -1);
      break;
    case CK_Down:
      wblock_input_move_cursor_y (wb, 1);
      break;
    case CK_PageUp:
      wblock_input_move_cursor_y (wb, -wb->lines/3);
      break;
    case CK_PageDown:
      wblock_input_move_cursor_y (wb, wb->lines/3);
      break;
    case CK_Left:
      wblock_input_decr_cursor_x (wb);
      break;
    case CK_Right:
      wblock_input_incr_cursor_x (wb);
      break;
    case CK_Home:
      data->offset_x=0;
      wb->cursor_x=0;
      break;
    case CK_End:
      data->offset_x=wblock_input_current_line (wb)->len - wb->cols;
      wb->cursor_x=wb->lines-1;
      break;
    case CK_BackSpace:
      wblock_input_backspace (wb);
      break;
    case CK_InsertChar:
      g_array_insert_val (
        wblock_input_current_line (wb),
        data->offset_x + wb->cursor_x,
        parm);
      wblock_input_incr_cursor_x (wb);
      wb->redraw=TRUE;
      break;
    default:
      return FALSE;
  }
  return TRUE;
}



static void
wblock_input_destroy (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  GArray *buf = data->buf;
  buf_to_string (buf, data->result);
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
  if (data->buf->len==0)
    buf_append_lines (data->buf, strdup("")); /*insert blank line*/
  wblock_init (wb, wblock_input_mouse, wblock_input_key, wblock_input_destroy, wblock_input_draw, data);
  return wb;
}
