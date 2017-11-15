#include <config.h>
#include "lib/global.h"
#include "lib/tty/tty.h"
#include "lib/skin.h" /*EDITOR_NORMAL_COLOR*/

#include "wblock.h"

void
wblock_frame_draw (WBlock *wb, int y0, int x0, int y, int x, int lines, int cols, gboolean do_draw) {
  const char *label = FRAME_DATA (wb->wdata)->label;
  int lines0 = wb->lines,
      cols0 = wb->cols;

  if (do_draw) {
    gboolean    draw_UL = IN_RECTANGLE (y0,         x0,            y,x,lines,cols),
                draw_UR = IN_RECTANGLE (y0,         x0+cols0-1,    y,x,lines,cols),
                draw_LL = IN_RECTANGLE (y0+lines0-1,x0,            y,x,lines,cols),
                draw_LR = IN_RECTANGLE (y0+lines0-1,x0+cols0-1,    y,x,lines,cols),
                draw_X  = x0+1<x+cols-1  && x0+cols0-1>=x+1,
                draw_bound_UP = (y0>=y && y0<=y+lines-1 && draw_X),
                draw_bound_LO = (y0+lines0-1>=y && y0+lines0-1<=y+lines-1 && draw_X),
                draw_Y  = y0<=y+lines-1 && y0+lines0-1>=y,
                draw_bound_LE = x0>=x && x0<=x+lines-1 && draw_Y,
                draw_bound_RI = x0+cols0-1>=x && x0+cols0-1<=x+cols-1 && draw_Y;

    if (draw_UL) {
      tty_gotoyx (y0,x0);
      tty_print_alt_char (ACS_ULCORNER, FALSE);
    }

    if (draw_UR) {
      tty_gotoyx (y0,x0+cols0-1);
      tty_print_alt_char (ACS_URCORNER, FALSE);
    }

    if (draw_LL) {
      tty_gotoyx (y0+lines0-1,x0);
      tty_print_alt_char (ACS_LLCORNER, FALSE);
    }

    if (draw_LR) {
      tty_gotoyx (y0+lines0-1,x0+cols0-1);
      tty_print_alt_char (ACS_LRCORNER, FALSE);
    }

    if (draw_bound_UP || draw_bound_LO) {
      int xl=MAX(x0+1,x+1),
          xr=MIN(x0+cols0-1,x+cols-1);

      if (draw_bound_UP) {
        tty_draw_hline (y0, xl, ACS_HLINE, xr-xl);
        if (label) {
          const char *p = label;
          int xc = x0+cols0/2-strlen(label)/2;
          while (*p) {
            if (YX_IN_WIDGET (wb,y0,xc)) {
              tty_gotoyx (y0,xc);
              tty_print_char (*p);
            }
            p++;
            xc++;
          }
        }
      }
      if (draw_bound_LO)
        tty_draw_hline (y0+lines0-1, xl, ACS_HLINE, xr-xl);
    }

    if (draw_bound_LE || draw_bound_RI) {
      int yu = y0>=y ? y0+1 : y,
          yl = y0+lines0<=y+lines?y0+lines0-1:y+lines;

      if (draw_bound_LE)
        tty_draw_vline (yu, x0, ACS_VLINE, yl-yu);
      if (draw_bound_RI)
        tty_draw_vline (yu, x0+cols0-1, ACS_VLINE, yl-yu);
    }
  }

  wblock_dfl_draw (wb,
    y0+1,
    x0+1,
    y0>=y ? y+1 : y,
    x0>=x ? x+1 : x,
    y0+lines0<=y+lines ? lines-2 : lines-1,
    x0+cols0<=x+cols ? cols-2 : cols-1,
    do_draw);

  if (!do_draw) {
    wb->cols = MAX (MAX (wb->cols,3), label ? strlen(label):0);
    wb->cols+=2;
    wb->lines = MAX (wb->lines, 0);
    wb->lines+=2;
  }
}

WBlock *
wblock_frame_new (char *label) {
  WBlock *wb = g_new0 (WBlock, 1);
  FrameData *data = g_new (FrameData, 1);
  data->label = label;
  data->color = EDITOR_NORMAL_COLOR;
  wblock_init (wb, NULL, NULL, NULL, wblock_frame_draw, data);
  wb->style.width_type = WIDTH_MAX;
  return wb;
}
