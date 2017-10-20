#include <config.h>
#include <stdlib.h>
#include <stdio.h>


#include "lib/global.h"
#include "src/mcgdb-bp.h"

static GList * mcgdb_bps = NULL;

#define MCGDB_BP(l) ((mcgdb_bp *)(l->data))

int mcgdb_bp_color_wait_remove;
int mcgdb_bp_color_wait_insert;
int mcgdb_bp_color_normal;
int mcgdb_bp_color_disabled;


void
mcgdb_bp_module_init (void) {
}

void
mcgdb_bp_module_free (void) {
  if (mcgdb_bps) {
    mcgdb_bp_remove_all ();
  }
}

mcgdb_bp *
mcgdb_bp_get (const char *filename, long line) {
  GList *l;
  if (!mcgdb_bps)
    return 0;
  for (l=mcgdb_bps;l!=NULL;l=l->next) {
    mcgdb *bp = MCGDB_BP(l);
    if (bp->line==line && !strcmp(bp->filename,filename)) {
      return bp;
    }
  }
  return NULL;
}


static void
free_bp (mcgdb_bp * bp) {
  free (bp->filename);
  free (bp->condition);
  free (bp);
}

void
mcgdb_bp_remove (char *filename, long line) {
  GList *l;
  mcgdb_bp *bp;
  for(l=mcgdb_bps;l!=NULL;l=l->next) {
    bp = MCGDB_BP(l);
    if (!strcmp(bp->filename,filename) && bp->line==line) {
      mcgdb_bps = g_list_remove_link (mcgdb_bps, l);
      free_bp (bp);
      g_list_free (l);
      return;
    }
  }
}

void
mcgdb_bp_remove_all (void) {
  if (!mcgdb_bps)
    return;
  g_list_free_full (mcgdb_bps,free_bp);
  mcgdb_bps = NULL;
}

int
mcgdb_bp_color(mcgdb_bp * bp) {
  if (bp->disabled) {
    return mcgdb_bp_color_disabled;
  }
  else {
    switch(bp->type) {
      case BP_WAIT_DELETE:
        return mcgdb_bp_color_wait_remove;
      case BP_WAIT_INSERT:
      case BP_WAIT_UPDATE:
        return mcgdb_bp_color_wait_insert;
      default:
        return mcgdb_bp_color_normal;
    }
  }
}

void
mcgdb_bp_disable(const char *filename, long line)

void
mcgdb_bp_insert (const char * filename, long line, bpwait wait, char * condition, gboolean disabled) {
  mcgdb_bp *bp;
  message_assert (mcgdb_bp_get (filename, line)==NULL);
  bp = g_new (mcgdb_bp, 1);
  bp->filename=strdup(filename);
  bp->line=line;
  bp->wait=wait;
  bp->condition=condition;
  bp->disabled=disabled;
  mcgdb_bps = g_list_append (mcgdb_bps,bp);
}

typedef enum {
  ASKBP_CANCEL=1,
  ASKBP_DELETE,
  ASKBP_UPDATE,
  ASKBP_CREATE,
  ASKBP_CHANGED,
  ASKBP_UNCHANGED,
} askbp_t;

static gboolean
ask_breakpoint_params_create (char ** condition, gboolean * disabled) {
  quick_widget_t quick_widgets[] = {
      QUICK_START_COLUMNS,
      //    QUICK_START_GROUPBOX (N_("Breakpoint")),
              QUICK_CHECKBOX (N_("&disable"), &disabled, NULL),
              QUICK_LABELED_INPUT (N_("condition:"), input_label_above, tab_spacing,
                                    "conditions", condition, NULL, FALSE, FALSE, INPUT_COMPLETE_NONE),
      QUICK_STOP_COLUMNS,
      QUICK_START_BUTTONS (TRUE, TRUE),
        QUICK_BUTTON (N_("&Create"), ASKBP_CREATE, NULL, NULL),
        QUICK_BUTTON (N_("&Cancel"), ASKBP_CANCEL, NULL, NULL),
      QUICK_END
  };

  quick_dialog_t qdlg = {
      -1, -1, 74,
      N_("Edit breakpoint"), "[Edit breakpoint]",
      quick_widgets, NULL, NULL
  };

  return quick_dialog (&qdlg) == B_CANCEL
}


static gboolean
ask_breakpoint_params_update (mcgdb_bp *bp) {
  gboolean disabled=bp->disabled;
  char * condition = strdup(bp->condition);
  quick_widget_t quick_widgets[] = {
      QUICK_START_COLUMNS,
      //    QUICK_START_GROUPBOX (N_("Breakpoint")),
              QUICK_CHECKBOX (N_("&disable"), &disabled, NULL),
              QUICK_LABELED_INPUT (N_("condition:"), input_label_above, tab_spacing,
                                    "conditions", &condition, NULL, FALSE, FALSE, INPUT_COMPLETE_NONE),

      QUICK_STOP_COLUMNS,
      QUICK_START_BUTTONS (TRUE, TRUE),
        QUICK_BUTTON (N_("&Update"), ASKBP_UPDATE, NULL, NULL),
        QUICK_BUTTON (N_("&Cancel"), ASKBP_CANCEL, NULL, NULL),
        QUICK_BUTTON (N_("&Delete"), ASKBP_DELETE, NULL, NULL),
      QUICK_END
  };

  quick_dialog_t qdlg = {
      -1, -1, 74,
      N_("Edit breakpoint"), "[Edit breakpoint]",
      quick_widgets, NULL, NULL
  };
  askbp_t res = quick_dialog (&qdlg);
  if (res==ASKBP_UPDATE) {
    askbp_t res2 = ((disabled==bp->disabled) && !strcmp(condition,bp->condition)) ? ASKBP_CHANGED : ASKBP_UNCHANGED;
    bp->disabled=disabled;
    free (bp->condition);
    bp->condition=condition;
    return res2;
  }
  else {
    return res;
  }
}


void
mcgdb_bp_process_click(const char *filename, long line, gboolean ask_cond) {
  mcgdb_bp * bp = mcgdb_bp_get (filename,line);
  char * condition = NULL;
  gboolean disabled = FALST, do_delete=FALSE;
  const char * action = NULL;
  json_t * resp;

  if (!bp) {
    if (ask_cond) {
      /*widget condition; will get disabled and condition*/
      askbp_t res = ask_breakpoint_params_create (&condition, &disabled);
      if (res==ASKBP_CANCEL) {
        return;
      }
    }
    mcgdb_bp_insert (strdup(filename),line,BP_WAIT_INSERT,condition,disabled);
    action="insert";
  }
  else {
    if (!ask_cond && !bp->condition) {
      switch(bp->type) {
        case BP_NORMAL:
          bp->type=BP_WAIT_DELETE;
          action="delete";
          break;
        case BP_DISABLED:
          bp->type=BP_WAIT_ENABLE;
          bp->disabled=FALSE;
          action = "update";
          break;
        case BP_WAIT_REMOVE:
          bp->type=BP_WAIT_INSERT;
          action = "insert";
          break;
        case BP_WAIT_INSERT:
          bp->type=BP_WAIT_DELETE;
          action = "delete"
          break;
        default:
      }
    }
    else {
      /* bp exists; just update condition or disable */
      ask_bp_t res = ask_breakpoint_params_change (bp);
      switch (res) {
        case ASKBP_DELETE:
          action="delete";
          bp->type=BP_WAIT_DELETE;
        case ASKBP_CHANGED:
          action="update";
          bp->type=BP_WAIT_UPDATE;
          break
        case ASKBP_CANCEL:
        case ASKBP_UNCHANGED:
        default:
          /*unchanged*/
          return
      }
    }
  }

  resp = json_object ();
  json_object_set_new(resp,"command",   json_string("break"));
  json_object_set_new(resp,"filename",  json_string(bp->filename));
  json_object_set_new(resp,"line",      json_integer(line));
  json_object_set_new(resp,"action",    json_string(action));
  if (!strcmp(action,"delete")) {
    json_object_set_new(resp,"disabled",json_boolean(bp->disabled));
    if (condition)
      json_object_set_new(resp,"condition",json_string(bp->condition));
  }
  sresp = json_dumps(resp,0);
  send_pkg_to_gdb (sresp);
  free (sresp);
  json_decref (resp);
}
