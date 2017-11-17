#ifndef __mcgdb_bp_widget_h__
#define __mcgdb_bp_widget_h__

#include "src/mcgdb-bp.h"

#define COLOR_BP_WAIT_UPDATE mcgdb_bp_color_wait_update
#define COLOR_BP_WAIT_DELETE mcgdb_bp_color_wait_remove


gboolean
breakpoints_edit_dialog (const char *filename, long line);

#endif
