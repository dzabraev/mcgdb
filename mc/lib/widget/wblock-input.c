#include <config.h>
#include "lib/global.h"
#include "lib/tty/tty.h"

#include "src/editor/editbuffer.h"
#include "src/keybind-defaults.h"

#include "wblock.h"

static int
count_lines (const char *buf) {
  int lines=1;
  while(*buf) {
    if (*(buf++)=='\n')
      lines++;
  }
  return lines;
}

static void
wblock_input_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  if (!do_draw) {
    wb->cols = cols;
    wb->lines = count_lines (data->buf);
  }
  else {
    char *str = data->buf[0];
    int skip_y = data->offset_y;
    int skip_x = data->offset_x;
    int ulen;
    int printed_lines=0;
    tty_setcolor (WBLOCK_INPUT_COLOR);
    tty_fill_region (y,x,wb->lines,wb->cols,' ');
    while (str && str[0] && printed_lines < (y-y0+lines)) {
      int skip_x0 = skip_x,
          printed_chars=0;
      tty_gotoyx (y0+printed_lines,x0);

      while (str[0] && skip_y>0) {
        skip_y--;
        goto net_line;
      }

      while (str[0] && skip_x0>0) {
        int ret;
        skip_x0--;
        get_utf (str, &ulen);
        str+=MAX(ulen,1);
      }

      while (str[0] && str[0]!='\n' && printed_chars<(x-x0+cols)) {
        int ch = get_utf (str, &ulen);
        if (g_unichar_isprint (c)) {
          tty_print_anychar (ch);
        }
        else {
          tty_print_anychar ('.');
          ulen=1;
        }
        str+=ulen;
        printed_chars++;
      }

      if (!str[0])
        break;

      printed_lines++;

      next_line: str = strchr (str,'\n');
      if (!str)
        break;
      else
        if (str[0]!=0)
          str++;
        else
          break;
    }
  }
}

static gboolean
wblock_input_mouse (WBlock *wb, mouse_msg_t msg, mouse_event_t * event) {

}

static void
wblock_input_insert_char (WBlock *wb, int c) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  g_array_append (data->buf, c);
  wb->redraw=TRUE;
}

GArray *
buf_get_line (GArray *buf, int y) {
  return g_array_index (buf, GArray *, y);
}


void
wblock_input_decr_cursor_x (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  if (data->cursor_x>0) {
    data->cursor_x--;
    wb->redraw=TRUE;
  }
  else {
    if (data->offset_x>0) {
      data->offset_x--;
      wb->redraw=TRUE;
    }
    else if (data->cursor_y>0 || data->offset_y>0) {
      if (data->cursor_y>0) {
        data->cursor_y--;
        wb->redraw=TRUE;
      }
      else if (data->offset_y>0) {
        data->offset_y--;
        wb->redraw=TRUE;
      }
      len = wblock_input_current_line (wb)->len;
      data->offset_x = len - wb->cols;
      data->cursor_x = wb->cols-1;
    }
  }
}

void
wblock_input_incr_cursor_x (WBlock *wb) {
  GArray *cur = wblock_input_current_line (wb);
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  if (data->cursor_x<wb->cols-1) {
    data->cursor_x++;
    wb->redraw=TRUE;
  }
  else {
    if (data->offset_x < cur->len - wb->lines-1) {
      data->offset_x++;
      wb->redraw=TRUE;
    }
    else if (data->cursor_y<wb->lines-1 || data->offset_y < data->buf->len - wb->lines - 1) {
      if (data->cursor_y<wb->lines-1) {
        data->cursor_y++;
        wb->redraw=TRUE;
      }
      else if (data->offset_y<data->buf->len - wb->lines - 1) {
        data->offset_y++;
        wb->redraw=TRUE;
      }
      data->offset_x = 0;
      data->cursor_x = 0;
    }
  }
}



void
wblock_input_move_cursor_y (WBlock *wb, int offset) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  int pos_x = data->cursor_x + data->offset_x;
  int pos_y;
  GArray *row;
  int add_cursor = offset > 0 ? MIN (offset, wb->lines - data->cursor_y) : MAX (offset, - data->cursor_y);
  int r = offset - add_cursor;
  int add_offset = r > 0 ? MIN (r, buf->len - wb->lines) : MAX (r, -data->offset_y);

  data->offset_y+=add_offset;
  data->cursor_y+=add_cursor;

  wb->redraw = wb->redraw || add_cursor!=0 || add_offset!=0;

  pos_y = data->offset_y + data->cursor_y;

  message_assert (data->offset_y>0 && data->cursor_y>0);

  row = buf_get_line (buf, pos_y);
  if (row->len < pos_x) {
    data->offset_x = MAX (0,row->len - wb->cols);
    data->cursor_x = wb->lines - 1;
  }
}

GArray *
wblock_input_current_line (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  int pos_y = data->offset_y + data->cursor_y;
  return g_array_index (data->buf, GArray *, pos_y);
}

void
wblock_input_remove_yx_ch (WBlock *wb, int y, int x) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  g_array_remove_index (buf_get_line (wb, y), x);
}

void
wblock_input_remove_cur_ch (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  wblock_input_remove_yx_ch (wb, data->offset_y+data->cursor_y, data->offset_x+data->cursor_x);
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
        int pos_y = data->offset_y + data->cursor_y;
        int pos_x = data->cursor_x + data->offset_x;
        GArray *row = wblock_input_current_line (wb);
        char *insert_data = row->len>pos_x ? ((char *)row->data) + pos_x : "";
        buf_insert_lines (buf, insert_data, pos_y+1); /*create new row*/
        g_array_remove_range (row, pos_x, buf->len-pos_x); /*remove copied data*/
        data->cursor_x = 0;
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
      data->cursor_x=0;
      break;
    case CK_End:
      data->offset_x=wblock_input_current_line (wb)->len - wb->cols;
      data->cursor_x=wb->lines-1;
      break
    case CK_Backspace:
      wblock_input_remove_cur_ch (wb);
    case CK_InsertChar:

  }
}

void buf_insert_char (GArray *buf, int y, int x, int ch) {
  g_array_index (
    g_array_index (buf, GArray *, y),
    char, x) = ch;
}

void
buf_insert_lines (GArray *buf, char *lines, int y) {
  char *line = lines;
  if (y==-1)
    y=buf->len;
  while (line) {
    int len;
    GArray *new_line = g_array_new (FALSE, FALSE, sizeof (char));
    next_line = strchr (line, '\n');
    len = next_line ? next_line - line : strlen (line);
    g_array_append_vals (new_line, line, len);
    if (y>=buf->len)
      g_array_append_val (buf, new_line);
    else
      g_array_insert_val (buf, y, new_line)
    y++;

    line = next_line
    if (line)
      line++; //skip \n
    else
      break;
  }
}

void
buf_append_lines (GArray *buf, char *lines) {
  buf_insert_lines (buf, lines, -1);
}

static void
buf_to_string (GArray *buf, char **string) {
  g_free (string[0]);
  string[0] = buf->len > 0 ? g_strdup (g_array_index (buf,GArray *, 0)->data) : NULL;
  for (int idx=1,size=buf->len;idx<size;idx++) {
    char *new_str
    g_strdup_printf (&new_str, "%s %s", string[0], g_array_index (buf,GArray *, idx)->data);
    g_free (string[0]);
    string[0] = new_str;
  }
}

void
wblock_input_destroy (WBlock *wb) {
  WBlockInputData *data = WBLOCK_INPUT_DATA (wb->wdata);
  GArray *buf = data->buf;
  buf_to_cstring (buf, data->result);
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
  if (slines.len==0)
    buf_append_lines (data->buf, ""); /*insert blank line*/
  wblock_init (wb, wblock_input_mouse, wblock_input_key, wblock_input_destroy, wblock_input_draw, data);
  return wb;
}
