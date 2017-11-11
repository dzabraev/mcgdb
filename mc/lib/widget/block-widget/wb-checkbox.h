#ifndef __block_checkbox_h__
#define __block_checkbox_h__

#define CHECKBOX_DATA(p) ((CheckboxData *)(p))

typedef struct CheckboxData {
  gchar *label;
  gboolean *flag;
} CheckboxData;

WBlock * wb_checkbox_new (char *label, gboolean *flag);

#endif