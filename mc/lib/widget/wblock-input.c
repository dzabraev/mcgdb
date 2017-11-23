#include <config.h>
#include "lib/global.h"
#include "lib/tty/tty.h"

#include "src/editor/editbuffer.h"

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

static gboolean
wblock_input_key (WBlock *wb, int parm) {
  int command = keybind_lookup_keymap_command (wblock_input_map, parm);
  switch (command) {
    case WB_INP_LEFT:
    case WB_INP_RIGHT:
    case WB_INT_UP:
    case WB_INT_DOWN:
    case WB_INT_PAGE_UP:
    case WB_INT_DOWN_UP:
    case WB_INT_ENTER:

    CK_Enter = 1L,
    CK_Up,
    CK_Down,
    CK_Left,
    CK_Right,
    CK_Home,
    CK_End,
    CK_LeftQuick,
    CK_RightQuick,
    CK_PageUp,
    CK_PageDown,


  }
}

WBlock * wblock_input_new (GArray *buf) {
  WBlockInputData *wb = g_new0 (WBlockInputData, 1);
  wb->buf = buf;
  wblock_init (wb, wblock_input_mouse, wblock_input_key, NULL, wblock_input_draw, data);
  return wb;
}
