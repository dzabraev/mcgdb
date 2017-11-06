#ifndef __mcgdb_bp_widget_h__
#define __mcgdb_bp_widget_h__

gboolean breakpoints_edit_dialog (const char *filename, long line);
gboolean is_bpw_dialog (WDialog *h);
cb_ret_t bpw_dialog_callback (Widget * w, Widget * sender, widget_msg_t msg, int parm, void *data);

#endif