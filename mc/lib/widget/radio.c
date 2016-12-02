/*
   Widgets for the Midnight Commander

   Copyright (C) 1994-2016
   Free Software Foundation, Inc.

   Authors:
   Radek Doulik, 1994, 1995
   Miguel de Icaza, 1994, 1995
   Jakub Jelinek, 1995
   Andrej Borsenkow, 1996
   Norbert Warmuth, 1997
   Andrew Borodin <aborodin@vmail.ru>, 2009, 2010, 2013, 2016

   This file is part of the Midnight Commander.

   The Midnight Commander is free software: you can redistribute it
   and/or modify it under the terms of the GNU General Public License as
   published by the Free Software Foundation, either version 3 of the License,
   or (at your option) any later version.

   The Midnight Commander is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

/** \file radio.c
 *  \brief Source: WRadui widget (radiobuttons)
 */

#include <config.h>

#include <stdlib.h>

#include "lib/global.h"

#include "lib/tty/tty.h"
#include "lib/widget.h"

/*** global variables ****************************************************************************/

/*** file scope macro definitions ****************************************************************/

/*** file scope type declarations ****************************************************************/

/*** file scope variables ************************************************************************/

/*** file scope functions ************************************************************************/

static cb_ret_t
radio_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data)
{
    WRadio *r = RADIO (w);
    int i;

    switch (msg)
    {
    case MSG_HOTKEY:
        {
            for (i = 0; i < r->count; i++)
            {
                if (r->texts[i].hotkey != NULL)
                {
                    int c = g_ascii_tolower ((gchar) r->texts[i].hotkey[0]);

                    if (c != parm)
                        continue;
                    r->pos = i;

                    /* Take action */
                    send_message (w, sender, MSG_KEY, ' ', data);
                    return MSG_HANDLED;
                }
            }
        }
        return MSG_NOT_HANDLED;

    case MSG_KEY:
        switch (parm)
        {
        case ' ':
            r->sel = r->pos;
            widget_set_state (w, WST_FOCUSED, TRUE);
            return MSG_HANDLED;

        case KEY_UP:
        case KEY_LEFT:
            if (r->pos > 0)
            {
                r->pos--;
                return MSG_HANDLED;
            }
            return MSG_NOT_HANDLED;

        case KEY_DOWN:
        case KEY_RIGHT:
            if (r->count - 1 > r->pos)
            {
                r->pos++;
                return MSG_HANDLED;
            }
        default:
            return MSG_NOT_HANDLED;
        }

    case MSG_CURSOR:
        widget_set_state (w, WST_FOCUSED, TRUE);
        widget_move (r, r->pos, 1);
        return MSG_HANDLED;

    case MSG_DRAW:
        {
            gboolean focused;

            focused = widget_get_state (w, WST_FOCUSED);

            for (i = 0; i < r->count; i++)
            {
                widget_selectcolor (w, i == r->pos && focused, FALSE);
                widget_move (w, i, 0);
                tty_draw_hline (w->y + i, w->x, ' ', w->cols);
                tty_print_string ((r->sel == i) ? "(*) " : "( ) ");
                hotkey_draw (w, r->texts[i], i == r->pos && focused);
            }

            return MSG_HANDLED;
        }

    case MSG_DESTROY:
        for (i = 0; i < r->count; i++)
            release_hotkey (r->texts[i]);
        g_free (r->texts);
        return MSG_HANDLED;

    default:
        return widget_default_callback (w, sender, msg, parm, data);
    }
}

/* --------------------------------------------------------------------------------------------- */

static void
radio_mouse_callback (Widget * w, mouse_msg_t msg, mouse_event_t * event)
{
    switch (msg)
    {
    case MSG_MOUSE_DOWN:
        RADIO (w)->pos = event->y;
        widget_select (w);
        break;

    case MSG_MOUSE_CLICK:
        RADIO (w)->pos = event->y;
        send_message (w, NULL, MSG_KEY, ' ', NULL);
        send_message (w->owner, w, MSG_POST_KEY, ' ', NULL);
        break;

    default:
        break;
    }
}

/* --------------------------------------------------------------------------------------------- */
/*** public functions ****************************************************************************/
/* --------------------------------------------------------------------------------------------- */

WRadio *
radio_new (int y, int x, int count, const char **texts)
{
    WRadio *r;
    Widget *w;
    int i, wmax = 0;

    r = g_new (WRadio, 1);
    w = WIDGET (r);

    /* Compute the longest string */
    r->texts = g_new (hotkey_t, count);

    for (i = 0; i < count; i++)
    {
        int width;

        r->texts[i] = parse_hotkey (texts[i]);
        width = hotkey_width (r->texts[i]);
        wmax = MAX (width, wmax);
    }

    /* 4 is width of "(*) " */
    widget_init (w, y, x, count, 4 + wmax, radio_callback, radio_mouse_callback);
    w->options |= WOP_SELECTABLE | WOP_WANT_CURSOR | WOP_WANT_HOTKEY;
    r->state = 1;
    r->pos = 0;
    r->sel = 0;
    r->count = count;

    return r;
}

/* --------------------------------------------------------------------------------------------- */
