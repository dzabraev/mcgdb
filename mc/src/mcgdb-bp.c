#include <config.h>
#include <stdlib.h>
#include <stdio.h>

#include <jansson.h>

#include "lib/global.h"

#include "src/mcgdb.h"
#include "src/mcgdb-bp.h"


static GList * mcgdb_bps = NULL;
static int id_counter=1;

#define MCGDB_BP(l) ((mcgdb_bp *)(l->data))

int mcgdb_bp_color_wait_remove;
int mcgdb_bp_color_wait_insert;
int mcgdb_bp_color_normal;
int mcgdb_bp_color_disabled;


static mcgdb_bp * mcgdb_bp_new (const char *filename, int line);
static void mcgdb_bp_free (mcgdb_bp * bp);
static GList * get_next_bp (GList *bpl, const char *filename, long line);
static int count_bps (const char *filename, long line);
static void json_append_upd_bp (json_t *jbps, const mcgdb_bp *bp);
static void json_append_del_bp (json_t *jbps, const mcgdb_bp *bp);
static void send_message_bp_update (const mcgdb_bp *bp);
static void send_message_bp_delete (const mcgdb_bp *bp);
static gboolean breakpoints_edit_dialog (const char *filename, long line);
static void delete_by_id (int id);
static mcgdb_bp * get_by_id (int id);
static mcgdb_bp * get_by_number (int number);
static void insert_bp_to_list (mcgdb_bp *bp);




void
mcgdb_bp_module_init (void) {
}

void
mcgdb_bp_module_free (void) {
  if (mcgdb_bps) {
    mcgdb_bp_remove_all ();
  }
}


gboolean
mcgdb_bp_remove (const char *filename, long line) {
  GList *l;
  mcgdb_bp *bp;
  for(l=mcgdb_bps;l!=NULL;l=l->next) {
    bp = MCGDB_BP(l);
    if (!strcmp(bp->filename,filename) && bp->line==line) {
      mcgdb_bps = g_list_remove_link (mcgdb_bps, l);
      mcgdb_bp_free (bp);
      g_list_free (l);
      return TRUE;
    }
  }
  return FALSE;
}

void
mcgdb_bp_remove_all (void) {
  if (!mcgdb_bps)
    return;
  g_list_free_full (mcgdb_bps,(void (*)(void *))mcgdb_bp_free);
  mcgdb_bps = NULL;
}


static GList *
get_next_bp (GList *bpl, const char *filename, long line) {
  while (bpl) {
    if (MCGDB_BP(bpl)->line==line && !strcmp(MCGDB_BP(bpl)->filename,filename))
      return bpl;
    else
      bpl = g_list_next (bpl);
  }
  return NULL;
}

static int
count_bps (const char *filename, long line) {
  int n=0;
  GList *bpl=mcgdb_bps;
  while (bpl) {
    bpl = get_next_bp (bpl,filename,line);
    if (bpl)
      n++;
    else
      return n;
    bpl= g_list_next (bpl);
  }
  return n;
}

static json_t *
get_common_breakpoints_pkg(void) {
  json_t *resp = json_object ();
  json_object_set_new (resp,"cmd",json_string ("onclick"));
  json_object_set_new (resp,"onclick",json_string ("breakpoints"));
  return resp;
}

static void
json_append_upd_bp (json_t *jbps, const mcgdb_bp *bp) {
  json_t * jbp = json_object ();
  json_object_set_new (jbp, "external_id", json_integer (bp->id));
  json_object_set_new (jbp, "enabled",      json_boolean (bp->enabled));
  json_object_set_new (jbp, "silent",       json_boolean (bp->silent));
  json_object_set_new (jbp, "ignore_count", json_integer (bp->ignore_count));
  json_object_set_new (jbp, "temporary",    json_boolean (bp->temporary));
  if (bp->thread!=-1)
    json_object_set_new (jbp, "thread", json_integer (bp->thread));
  if (bp->condition)
    json_object_set_new (jbp, "condition", json_string (bp->condition));
  if (bp->commands)
    json_object_set_new (jbp, "commands", json_string (bp->commands));
  if (bp->number!=-1)
    json_object_set_new (jbp, "number", json_integer (bp->number));

  json_object_set_new (jbp, "filename", json_string (bp->filename));
  json_object_set_new (jbp, "line", json_integer (bp->line));

  json_array_append_new (jbps,jbp);
}

static void
send_message_bp_update (const mcgdb_bp *bp) {
  json_t *resp = get_common_breakpoints_pkg ();
  json_t *bps = json_array ();
  json_append_upd_bp (bps,bp);
  json_object_set_new (resp,"update",bps);
  send_pkg_to_gdb (json_dumps (resp,0));
  json_decref (resp);
}

static void
json_append_del_bp (json_t *jbps, const mcgdb_bp *bp) {
  json_t * jbp = json_object ();
  json_object_set_new (jbp, "external_id", json_integer (bp->id));
  if (bp->number!=-1)
    json_object_set_new (jbp, "number", json_integer (bp->number));
  json_array_append_new (jbps,jbp);
}

static void
send_message_bp_delete (const mcgdb_bp *bp) {
  json_t *resp = get_common_breakpoints_pkg ();
  json_t *ids = json_array ();
  json_append_del_bp (ids,bp);
  json_object_set_new (resp,"delete",ids);
  send_pkg_to_gdb (json_dumps (resp,0));
  json_decref (resp);
}

static gboolean
breakpoints_edit_dialog (const char *filename, long line) {
  return FALSE;
}

static gboolean
bp_has_nondefault_vals(mcgdb_bp *bp) {
  return !(
  bp->enabled==TRUE      &&
  bp->silent==FALSE      &&
  bp->ignore_count==0    &&
  bp->temporary==FALSE   &&
  bp->thread==-1         &&
  bp->condition==NULL    &&
  bp->commands==NULL);

}

gboolean
mcgdb_bp_process_click (const char *filename, long line, gboolean open_menu) {
  int nbps;
  gboolean need_redraw=FALSE;
  if (!filename)
    return need_redraw;
  nbps = count_bps (filename,line);
  if (nbps>0) {
    if (nbps==1) {
      GList *bpl = get_next_bp (mcgdb_bps,filename,line);
      mcgdb_bp * bp = MCGDB_BP(bpl);
      if (bp_has_nondefault_vals(bp)) {
        need_redraw=breakpoints_edit_dialog (filename,line);
      }
      else {
        if (bp->wait_status==BP_NOWAIT || bp->wait_status==BP_WAIT_UPDATE) {
          bp->wait_status = BP_WAIT_DELETE;
          send_message_bp_delete (bp);
          need_redraw=TRUE;
        }
        else if (bp->wait_status==BP_WAIT_DELETE) {
          bp->wait_status = BP_WAIT_UPDATE;
          send_message_bp_update (bp);
          need_redraw=TRUE;
        }
      }
    }
    else {
      need_redraw=breakpoints_edit_dialog (filename,line);
    }
  }
  else {
    if (open_menu) {
      need_redraw=breakpoints_edit_dialog (filename,line);
    }
    else {
      mcgdb_bp *bp = mcgdb_bp_new (filename,line);
      insert_bp_to_list (bp);
      send_message_bp_update (bp);
      need_redraw=TRUE;
    }
  }
  return need_redraw;
}




int
mcgdb_bp_color(const char * filename, long line) {
  gboolean  exists_enable_no_cond=FALSE,
            exists_enable=FALSE,
            exists_disable=FALSE,
            exists_wait_del=FALSE,
            exists_wait_upd=FALSE;
  if (!filename)
    return -1;
  for(GList *l=mcgdb_bps;l!=NULL;l=l->next) {
    mcgdb_bp * bp = MCGDB_BP(l);
    if (mcgdb_current_thread_id!=-1 && bp->thread!=-1 && bp->thread!=mcgdb_current_thread_id)
      continue;
    if (bp->line!=line || strcmp(bp->filename,filename))
      continue;
    if (bp->wait_status==BP_NOWAIT) {
      if (bp->enabled) {
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
      switch (bp->wait_status) {
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
  bp->number=-1;
  bp->enabled=TRUE;
  bp->silent=FALSE;
  bp->ignore_count=0;
  bp->temporary=FALSE;
  bp->thread=-1;
  bp->condition=NULL;
  bp->commands=NULL;
  bp->filename=strdup(filename);
  bp->line=line;
  bp->id = id_counter++;
  bp->wait_status = BP_WAIT_UPDATE;
  return bp;
}



static void
delete_by_id (int id) {
  for(GList *l=mcgdb_bps;l!=NULL;l=l->next) {
    mcgdb_bp *bp = MCGDB_BP(l);
    if (bp->id==id) {
      mcgdb_bps = g_list_remove_link (mcgdb_bps, l);
      mcgdb_bp_free (bp);
      g_list_free (l);
      return;
    }
  }
}

static void
delete_by_number (int number) {
  for(GList *l=mcgdb_bps;l!=NULL;l=l->next) {
    mcgdb_bp *bp = MCGDB_BP(l);
    if (bp->number==number) {
      mcgdb_bps = g_list_remove_link (mcgdb_bps, l);
      mcgdb_bp_free (bp);
      g_list_free (l);
      return;
    }
  }
}


static mcgdb_bp *
get_by_id (int id) {
  for(GList *l=mcgdb_bps;l!=NULL;l=l->next) {
    mcgdb_bp *bp = MCGDB_BP(l);
    if (bp->id==id) {
      return bp;
    }
  }
  return NULL;
}

static mcgdb_bp *
get_by_number (int number) {
  for(GList *l=mcgdb_bps;l!=NULL;l=l->next) {
    mcgdb_bp *bp = MCGDB_BP(l);
    if (bp->number==number) {
      return bp;
    }
  }
  return NULL;
}


static void
insert_bp_to_list (mcgdb_bp *bp) {
  mcgdb_bps = g_list_append (mcgdb_bps, bp);
}

void pkg_bps_del(json_t *pkg) {
  json_t *ids = myjson_arr (pkg,"ids");
  mcgdb_bp * bp;
  int len = json_array_size (ids);
  int id=-1,number=-1;
  for (int i=0;i<len;i++) {
    json_t * bp_data = json_array_get (ids,i);
    json_t * tmp=NULL;
    tmp = json_object_get (bp_data, "external_id");
    if (tmp) {
      id = json_integer_value (tmp);
      bp = get_by_id (id);
      message_assert (bp!=NULL);
    }
    else {
      number = myjson_int (bp_data, "number");
      bp = get_by_number (number);
      message_assert (bp!=NULL);
    }
    if (bp->wait_status==BP_WAIT_UPDATE) {
      /* deletion canceled. waiting update package */
      continue;
    }
    if (id!=-1)
      delete_by_id (id);
    else if (number!=-1)
      delete_by_number (number);
    else
      message_assert (FALSE);
  }
}

void pkg_bps_upd(json_t *pkg) {
  json_t *bps_data = myjson_arr (pkg,"bps_data");
  int len = json_array_size (bps_data);
  for (int i=0;i<len;i++) {
    json_t *bp_data = json_array_get (bps_data,i);
    json_t *tmp;
    mcgdb_bp *bp=NULL;
    tmp = json_object_get (bp_data,"external_id");
    if (tmp) {
      int id = json_integer_value (tmp);
      bp = get_by_id (id);
      message_assert (bp!=NULL);
      if (bp->wait_status==BP_WAIT_DELETE) {
        /*this bp was created and quickly deleted. wait next that delete this breakpoint*/
        continue;
      }
    }
    else {
      const char * filename = myjson_str (bp_data,"filename");
      int line = myjson_int (bp_data,"line");
      tmp = json_object_get (bp_data,"number");
      if (tmp) {
        int number = json_integer_value (tmp);
        bp = get_by_number (number);
      }
      if (!bp) {
        bp = mcgdb_bp_new (filename,line);
        insert_bp_to_list (bp);
      }
    }

    bp->wait_status = BP_NOWAIT;

    tmp = json_object_get (bp_data,"number");
    if (tmp)
      bp->number=json_integer_value (tmp);

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

    bp->hit_count = myjson_int (bp_data, "hit_count");

    tmp = json_object_get (bp_data,"condition");
    if (tmp) {
      if (bp->condition)
        g_free (bp->condition);
      bp->condition = strdup (json_string_value (tmp));
    }

    tmp = json_object_get (bp_data,"commands");
    if (tmp) {
      if (bp->commands)
        g_free (bp->commands);
      bp->commands = strdup (json_string_value (tmp));
    }
  }
}





