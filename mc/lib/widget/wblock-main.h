#ifndef __wblock_main_h__
#define __wblock_main_h__

#define WBMAIN(w) ((WBlockMain *)(w))
#define WBM_UPDATE_COORDS(wbm) wbm_wblock_draw(wbm,FALSE)
#define WBM_REDRAW(wbm) wbm_wblock_draw (wbm,TRUE);
#define WIDGET_ENTRY(l) ((WbmWidgetEntry *)(l->data))

typedef struct WBlockMain WBlockMain;
typedef struct WbmWidgetEntry WbmWidgetEntry;

typedef void (*pos_callback_t) (WbmWidgetEntry *entry);


typedef struct WbmWidgetEntry {
  WBlock *wb;
  WBlockMain *wbm;
  WBlock *selected_widget;
  pos_callback_t calcpos;
  gpointer calcpos_data;
  gboolean with_frame;
  int offset;
  int y;
  int x;
  int lines;
  int cols;
} WbmWidgetEntry;


typedef struct WBlockMain {
  Widget w;
  WbmWidgetEntry *selected_entry;
  gboolean redraw;
  GList *widget_entries;
} WBlockMain;

typedef struct {
  int y;
  int x;
  int lines;
  int cols;
  gboolean closest_to_y;
} CalcposData;

WBlockMain *wblock_main_new (void);

void wblock_main_add_widget (
  WBlockMain *wbm,
  WBlock *wb,
  pos_callback_t calcpos,
  gpointer calcpos_data,
  gboolean with_frame
);

int  wblock_main_run  (WBlockMain *wbm);
void wblock_main_free (WBlockMain *wbm);
void wblock_main_save (WBlockMain *wbm);


CalcposData * calcpos_data_new (void);
void calcpos_data_free (CalcposData *calcpos_data);
void default_calcpos (WbmWidgetEntry *wbm);


#endif
