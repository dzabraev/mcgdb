#include <config.h>
#include <stdlib.h>
#include <stdio.h>


#include "lib/global.h"
#include "src/mcgdb-bp.h"

static GList * mcgdb_bps = NULL;
static int id_counter=1;

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





















int
mcgdb_bp_color(const char * filename, int line) {
  gboolean  exists_enable_no_cond=FALSE,
            exists_enable=FALSE,
            exists_disable=FALSE,
            exists_wait_del=FALSE,
            exists_wait_upd=FALSE;
  message_assert (mcgdb_current_thread_id!=-1);

  for(l=mcgdb_bps;l!=NULL;l=l->next) {
    bp = MCGDB_BP(l);
    if (bp->thread!=-1 && bp->thread!=mcgdb_current_thread_id)
      continue;
    if (bp->line!=line || strcmp(bp->filename,filename))
      continue;
    if (bp->wait_status==BP_NOWAIT) {
      if (bp->enable) {
        exists_enable=TRUE;
        if (!bp->condition) {
          exists_enable_no_cond=TRUE;
        }
      }
      else {
        exists_disable=TRUE;
      }
    }
    else {
      switch (bp->type) {
        case BP_WAIT_UPDATE:
          exists_wait_upd=TRUE;
          break;
        case BP_WAIT_DELETE:
          exists_wait_del=TRUE;
          break;
        default:
          break;
      }
    }
  }

  if (exists_wait_upd)
    return mcgdb_bp_color_wait_insert;
  else if (exists_wait_del)
    return mcgdb_bp_color_wait_remove;
  else if (exists_enable_no_cond)
    return mcgdb_bp_color_normal;
  else if (exists_enable)
    return mcgdb_bp_color_normal;
  else if (exists_disable)
    return mcgdb_bp_color_disabled;
  else
    return -1;
}

static void
mcgdb_bp_free (mcgdb_bp * bp) {
  message_assert (bp->filename!=NULL);
  g_free (bp->filename);
  if (bp->condition)
    g_free (bp->condition);
  if (bp->commands)
    g_free (bp->commands);
  g_free (bp);
}


static mcgdb_bp *
mcgdb_bp_new (const char *filename, int line) {
  mcgdb_bp * bp = g_new(mcgdb_bp,1);
  bp->enabled=TRUE;
  bp->silent=FALSE;
  bp->ignore_count=0;
  bp->temporary=FALSE;
  bp->thread=-1;
  bp->condition=NULL;
  bp->commands=NULL;
  bp->filename=strdup(filename);
  bp->line=line;
  bp->id = bp_counter++;
  bp->wait_status = BP_WAIT_UPDATE;
  return bp;
}



static void
delete_by_id (int id) {
  for(l=mcgdb_bps;l!=NULL;l=l->next) {
    bp = MCGDB_BP(l);
    if (bp->id==id) {
      mcgdb_bps = g_list_remove_link (mcgdb_bps, l);
      free_bp (bp);
      g_list_free (l);
      return;
    }
  }
}

static mcgdb_bp *
get_by_id (int id) {
  for(l=mcgdb_bps;l!=NULL;l=l->next) {
    bp = MCGDB_BP(l);
    if (bp->id==id) {
      return bp
    }
  }
  return NULL;
}

static void
insert_bp_to_list (mcgdb *bp) {
  mcgdb_bps = g_list_append (mcgdb_bp, bp);
}

void pkg_bps_del(json_t *pkg) {
  json_t *ids = myjson_array (pkg,"ids");
  mcgdb_bp * bp;
  int len = json_array_size (ids);
  for (int i=0;i<len;i++) {
    int id = json_integer_value (json_array_get (ids,i));
    bp = get_by_id (id);
    if (bp->wait_status==BP_WAIT_UPDATE) {
      /* deletion canceled. waiting update package */
      continue
    }
    delete_by_id (id);
  }
}

void pkg_bps_update(json_t *pkg) {
  json_t *bps_data = myjson_array (pkg,"bps_data");
  int len = json_array_size (bps_data);
  for (int i=0;i<len;i++) {
    json_t *bp_data = json_array_get (bps_data,i);
    json_t *tmp;
    mcgdb_bp *bp
    tmp = json_object_get (bp_data,"external_id");
    if (tmp) {
      int id = json_integer_value (tmp)
      bp = get_by_id (id);
      if (bp->wait_status==BP_WAIT_DELETE) {
        /*this bp was created and quickly deleted. wait next that delete this breakpoint*/
        continue;
      }
      message_asstert (bp!=NULL);
    }
    else {
      const char * filename = myjson_str (bp_data,"filename");
      int line = myjson_int (bp_data,"line");
      bp = mcgdb_bp_new (filename,line);
      insert_bp_to_list (bp);
    }

    tmp = json_object_get (bp_data,"enabled");
    if (tmp)
      bp->enabled=json_boolean_value (tmp);

    tmp = json_object_get (bp_data,"silent");
    if (tmp)
      bp->silent=json_boolean_value (tmp);

    tmp = json_object_get (bp_data,"ignore_count");
    if (tmp)
      bp->ignore_count = json_integer_value (tmp);

    tmp = json_object_get (bp_data,"temporary");
    if (tmp)
      bp->temporary = json_boolean_value (tmp);

    tmp = json_object_get (bp_data,"thread");
    if (tmp)
      bp->thread = json_integer_value (tmp);

    tmp = json_object_get (bp_data,"condition");
    if (tmp) {
      if (bp->condition)
        g_free (bp->condition);
      bp->condition = strdup (json_integer_value (tmp));
    }

    tmp = json_object_get (bp_data,"commands");
    if (tmp) {
      if (bp->commands)
        g_free (bp->commands);
      bp->commands = strdup (json_integer_value (tmp));
    }
  }
}





