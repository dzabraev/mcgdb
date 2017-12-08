#include <config.h>

#include "lib/global.h"
#include <strings.h>
#include "src/keybind-defaults.h" /*bpw_map*/
#include "src/mcgdb.h"
#include "lib/widget/wblock.h"
#include "lib/skin.h" /*EDITOR_NORMAL_COLOR*/
#include "lib/tty/tty.h"



WBlock *
wblock_get_widget_yx (WBlock *wb, int y, int x) {
  for (GList *l=g_list_last (wb->widgets);l;l=l->prev) {
    WBlock *c = WBLOCK (l->data);
    /*We should fall into most depth widgets becuse coordinates of
      child elements may doesn't belong to parent's coordinate rectangle*/
    WBlock *most_depth = wblock_get_widget_yx (c, y, x);
    if (most_depth)
      return most_depth;
  }
  if (YX_IN_WIDGET (wb,y,x))
    return wb;
  else
    return NULL;
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
      tty_setcolor (c->style.color);
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
    wblock_destroy (WBLOCK (l->data));
  }
  g_list_free_full (wb->widgets, g_free);
  g_free (wb->name);
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
  wblock_set_color (wb, WBLOCK_COLOR_NORMAL);
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
wblock_add_const_widget (WBlock * wb, WBlock * widget) {
  WBlock *parent = wblock_empty ();
  wblock_set_destroy (parent, NULL); /*disable clear childs*/
  wblock_add_widget (parent, widget);
  wb->widgets = g_list_append (wb->widgets, parent);
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


WBlockMain *
wblock_get_wbm (WBlock *wb) {
  WBlock *p = wb->parent, *q=wb;
  while (p) {
    q=p;
    p=p->parent;
  }
  return q->entry->wbm;
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

char *
strstrip (const char *str) {
  const char *p1,*p2;
  size_t len;

  if (!str)
    return NULL;

  len = strlen (str);

  if (!len)
    return NULL;

  p1 = str;
  p2 = p1 + len - 1;

  while (p2-p1>0 && isspace (*p1)) {p1++;}

  if (p2-p1==0 && isspace(*p2))
    return NULL;

  while (isspace (*p2)) {p2--;}

  return g_strndup (p1, p2-p1+1);
}

void
wblock_set_color (WBlock *wb, int color) {
  if (wb->style.color != color) {
    wb->style.color = color;
    wb->redraw = TRUE;
  }
}

void
wblock_destroy (WBlock *wb) {
  if (wb->destroy)
    wb->destroy (wb);
}

void
wblock_unlink (WBlock *wb) {
  if (!wb->parent)
    return;
  wb->parent->widgets = g_list_remove (wb->parent->widgets, wb);
  wb->parent = NULL;
}

WBlock *
wblock_set_name (WBlock *wb, char *name) {
  wb->name = name;
  return wb;
}

WBlock *
find_closest_by_name (WBlock *wb, const char *name) {
  /*currently search only in parents*/
  WBlock *p = wb->parent;
  while (p) {
    if (p->name && !strcmp (p->name,name)) {
      return p;
    }
  }
  return NULL;
}
