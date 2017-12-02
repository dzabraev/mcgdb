#include <config.h>
#include <stdlib.h>
#include <stdio.h>

#include <jansson.h>

#include "lib/global.h"

#include "src/mcgdb.h"
#include "src/mcgdb-bp.h"
#include "src/mcgdb-bp-widget.h"

#include "src/editor/edit-impl.h" // LINE_STATE_WIDTH

GList * mcgdb_bps = NULL;
static int id_counter=1;

int mcgdb_bp_color_wait_remove;
int mcgdb_bp_color_wait_update;
int mcgdb_bp_color_normal;
int mcgdb_bp_color_disabled;
int mcgdb_bp_frame_color_wait_delete;

static void mcgdb_bp_add_location (mcgdb_bp *bp, const char *filename, int line);
static void mcgdb_bp_clear_locations (mcgdb_bp *bp);
static void delete_by_id (int id);
static mcgdb_bp * get_by_id (int id);
static mcgdb_bp * get_by_number (int number);
static int mcgdb_bp_remove (const char *filename, long line);

static json_t * breakpoints_pkg(void);
static json_t * get_bp_data (const mcgdb_bp *bp);
static json_t * get_bp_del_data (const mcgdb_bp *bp);
static void     append_update_bp (json_t *pkg, const mcgdb_bp *bp);
static void     append_delete_bp (json_t *pkg, const mcgdb_bp *bp);
static json_t * pkg_update_bp (const mcgdb_bp *bp);
static json_t * pkg_delete_bp (const mcgdb_bp *bp);
static void send_pkg (json_t *pkg);



static bp_loc_t *bp_loc_new (const char *filename, int line);
static void bp_loc_free (bp_loc_t *loc);
static bp_loc_t * bp_loc_copy (const bp_loc_t * loc);
static gpointer gcopyfunc_bp_loc_copy (gconstpointer src, gpointer data);
static gboolean bp_locs_compare (const bp_loc_t *loc1, const bp_loc_t *loc2);

gboolean mcgdb_bp_has_location (const mcgdb_bp *bp, const char *filename, int line);
gboolean mcgdb_bp_has_loc (const mcgdb_bp *bp, const_bp_loc_t *loc);
gboolean mcgdb_bp_has_not_loc (const mcgdb_bp *bp, const_bp_loc_t *loc);
static GList * mcgdb_bp_find_bp_with_loc (GList *bpl, const_bp_loc_t *loc);






static bp_loc_t *
bp_loc_new (const char *filename, int line) {
  bp_loc_t *loc = g_new (bp_loc_t,1);
  loc->filename = strdup(filename);
  message_assert (loc->filename!=NULL);
  loc->line = line;
  return loc;
}

static bp_loc_t *
bp_loc_copy (const bp_loc_t * loc) {
  bp_loc_t *newloc = g_new (bp_loc_t,1);
  newloc->filename = strdup (loc->filename);
  newloc->line = loc->line;
  return newloc;
}

static void
bp_loc_free (bp_loc_t *loc) {
  free (loc->filename);
  free (loc);
}

static gboolean
bp_locs_compare (const bp_loc_t *loc1, const bp_loc_t *loc2) {
  return !(loc1->line==loc2->line && !strcmp(loc1->filename,loc2->filename));
}



void
mcgdb_bp_module_init (void) {
}

void
mcgdb_bp_module_free (void) {
  if (mcgdb_bps) {
    mcgdb_bp_remove_all ();
  }
}


static int
mcgdb_bp_remove (const char *filename, long line) {
  const_bp_loc_t loc = {.filename=filename,.line=line};
  GList * l = mcgdb_bp_find_bp_with_loc (mcgdb_bps,&loc);
  int n=0;
  while (l) {
    GList *next = mcgdb_bp_find_bp_with_loc (l->next,&loc);
    mcgdb_bps = g_list_remove_link (mcgdb_bps, l);
    mcgdb_bp_free (MCGDB_BP(l));
    g_list_free (l);
    l=next;
    n+=1;
  }

  return n;
}

void
mcgdb_bp_remove_all (void) {
  if (!mcgdb_bps)
    return;
  g_list_free_full (mcgdb_bps,(void (*)(void *))mcgdb_bp_free);
  mcgdb_bps = NULL;
}


static json_t *
breakpoints_pkg(void) {
  json_t *resp = json_object ();
  json_object_set_new (resp,"cmd",json_string ("onclick"));
  json_object_set_new (resp,"onclick",json_string ("breakpoints"));
  json_object_set_new (resp,"update",json_array ());
  json_object_set_new (resp,"delete",json_array ());
  return resp;
}

static json_t *
get_bp_data (const mcgdb_bp *bp) {
  json_t * bp_data = json_object ();
  json_object_set_new (bp_data, "external_id", json_integer (bp->id));
  json_object_set_new (bp_data, "enabled",      json_boolean (bp->enabled));
  json_object_set_new (bp_data, "silent",       json_boolean (bp->silent));
  json_object_set_new (bp_data, "ignore_count", json_integer (bp->ignore_count));
  json_object_set_new (bp_data, "temporary",    json_boolean (bp->temporary));
  json_object_set_new (bp_data, "thread", json_integer (bp->thread));
  json_object_set_new (bp_data, "condition", json_string (bp->condition));
  json_object_set_new (bp_data, "commands", json_string (bp->commands));
  if (bp->number!=-1)
    json_object_set_new (bp_data, "number", json_integer (bp->number));
  if (bp->create_loc)
    json_object_set_new (bp_data, "create_loc", json_string (bp->create_loc));

  return bp_data;
}


static json_t *
get_bp_del_data (const mcgdb_bp *bp) {
  json_t * jbp = json_object ();
  json_object_set_new (jbp, "external_id", json_integer (bp->id));
  if (bp->number!=-1)
    json_object_set_new (jbp, "number", json_integer (bp->number));
  return jbp;
}


static void
append_update_bp (json_t *pkg, const mcgdb_bp *bp) {
  json_array_append_new (json_object_get (pkg,"update"),get_bp_data (bp));
}

static void
append_delete_bp (json_t *pkg, const mcgdb_bp *bp) {
  json_array_append_new (json_object_get (pkg,"delete"),get_bp_del_data (bp));
}

static json_t *
pkg_update_bp (const mcgdb_bp *bp) {
  json_t *pkg = breakpoints_pkg ();
  append_update_bp (pkg,bp);
  return pkg;
}

static json_t *
pkg_delete_bp (const mcgdb_bp *bp) {
  json_t *pkg = breakpoints_pkg ();
  append_delete_bp (pkg,bp);
  return pkg;
}


static void
send_pkg (json_t *pkg) {
  char *resp = json_dumps (pkg,0);
  send_pkg_to_gdb (resp);
  json_decref (pkg);
  free (resp);
}

void
send_pkg_delete_bp (const mcgdb_bp * bp) {
  return send_pkg(pkg_delete_bp(bp));
}

void
send_pkg_update_bp (const mcgdb_bp * bp) {
  return send_pkg(pkg_update_bp(bp));
}

gboolean
mcgdb_bp_has_loc (const mcgdb_bp *bp, const_bp_loc_t *loc) {
  return g_list_find_custom (bp->locations, loc, (GCompareFunc)bp_locs_compare)!=NULL;
}

gboolean
mcgdb_bp_has_not_loc (const mcgdb_bp *bp, const_bp_loc_t *loc) {
  return !mcgdb_bp_has_loc (bp,loc);
}



gboolean
mcgdb_bp_has_location (const mcgdb_bp *bp, const char *filename, int line) {
  const_bp_loc_t loc = {.filename=filename,.line=line};
  return mcgdb_bp_has_loc (bp,&loc);
}


static GList *
mcgdb_bp_find_bp_with_loc (GList *bpl, const_bp_loc_t *loc) {
  return g_list_find_custom (bpl,loc,(GCompareFunc)mcgdb_bp_has_not_loc);
}

GList *
mcgdb_bp_find_bp_with_location (GList *bpl, const char *filename, int line) {
  const_bp_loc_t loc = {.filename=filename,.line=line};
  return mcgdb_bp_find_bp_with_loc (bpl,&loc);
}



int
count_bps (const char *filename, long line) {
  int n=0;
  const_bp_loc_t loc = {.filename=filename,.line=line};
  GList *bpl=mcgdb_bps;
  while (bpl) {
    bpl = mcgdb_bp_find_bp_with_loc (bpl,&loc);
    if (bpl) {
      n++;
      bpl = g_list_next (bpl);
    }
    else {
      return n;
    }
  }
  return n;
}


void
mcgdb_create_bp (const char *filename, long line) {
  mcgdb_bp *bp = mcgdb_bp_new ();
  mcgdb_bp_add_location (bp,filename,line);
  bp->create_loc = g_strdup_printf ("%s:%lu",filename,line);
  insert_bp_to_list (bp);
  send_pkg_update_bp (bp);
}

gboolean
mcgdb_bp_process_click (const char *filename, long line, int click_y, int click_x) {
  int nbps;
  gboolean need_redraw=FALSE;
  gboolean open_menu = click_x<LINE_STATE_WIDTH;
  if (!filename)
    return need_redraw;
  nbps = count_bps (filename,line);
  if (nbps>0) {
    need_redraw=breakpoints_edit_dialog (filename, line, click_y, click_x);
  }
  else {
    mcgdb_create_bp (filename, line);
    need_redraw=TRUE;
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
    if (selected_thread_global_num!=-1 && bp->thread!=-1 && bp->thread!=selected_thread_global_num)
      continue;
    if (!mcgdb_bp_has_location (bp,filename,line))
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
    return mcgdb_bp_color_wait_update;
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
mcgdb_bp_add_location (mcgdb_bp *bp, const char *filename, int line) {
  bp_loc_t *loc = bp_loc_new (filename,line);
  bp->locations = g_list_append (bp->locations, loc);
}

static void
mcgdb_bp_clear_locations (mcgdb_bp *bp) {
  g_list_free_full (bp->locations, (GDestroyNotify)bp_loc_free);
  bp->locations = NULL;
}

void
mcgdb_bp_free (mcgdb_bp * bp) {
  mcgdb_bp_clear_locations (bp);
  if (bp->condition)
    g_free (bp->condition);
  if (bp->commands)
    g_free (bp->commands);
  g_free (bp);
}


mcgdb_bp *
mcgdb_bp_new (void) {
  mcgdb_bp * bp = g_new(mcgdb_bp,1);
  bp->number=-1;
  bp->enabled=TRUE;
  bp->silent=FALSE;
  bp->ignore_count=0;
  bp->hit_count=0;
  bp->temporary=FALSE;
  bp->thread=-1;
  bp->condition=NULL;
  bp->commands=NULL;
  bp->id = id_counter++;
  bp->wait_status = BP_WAIT_UPDATE;
  bp->locations=NULL;
  bp->create_loc=NULL;
  return bp;
}

void
mcgdb_bp_copy_to (const mcgdb_bp * bp, mcgdb_bp * bp_new) {
  bp_new->number        = bp->number        ;
  bp_new->enabled       = bp->enabled       ;
  bp_new->silent        = bp->silent        ;
  bp_new->ignore_count  = bp->ignore_count  ;
  bp_new->hit_count     = bp->hit_count     ;
  bp_new->temporary     = bp->temporary     ;
  bp_new->thread        = bp->thread        ;
  bp_new->condition     = g_strdup (bp->condition);
  bp_new->commands      = g_strdup (bp->commands);
  bp_new->id            = bp->id            ;
  bp_new->wait_status   = bp->wait_status   ;
  //bp_new->locations     = g_list_copy_deep (bp->locations, gcopyfunc_bp_loc_copy, NULL);
  {
    bp_new->locations = NULL;
    for (GList *l = bp->locations;l;l=l->next) {
      bp_new->locations = g_list_append (bp_new->locations, bp_loc_copy (l->data));
    }
  }
  bp_new->create_loc = bp->create_loc;
}

gboolean
mcgdb_bp_equals (const mcgdb_bp *bp1, const mcgdb_bp *bp2) {
  return
    bp1->number        == bp2->number        &&
    bp1->enabled       == bp2->enabled       &&
    bp1->silent        == bp2->silent        &&
    bp1->ignore_count  == bp2->ignore_count  &&
    bp1->temporary     == bp2->temporary     &&
    bp1->thread        == bp2->thread        &&
    bp1->condition     == bp2->condition     &&
    bp1->commands      == bp2->commands      &&
    bp1->id            == bp2->id            ;
}

void
mcgdb_bp_assign (mcgdb_bp *bp1, const mcgdb_bp *bp2) {
  bp1->enabled      = bp2->enabled       ;
  bp1->silent       = bp2->silent        ;
  bp1->ignore_count = bp2->ignore_count  ;
  bp1->thread       = bp2->thread        ;
  bp1->wait_status  = bp2->wait_status   ;

  g_free (bp1->condition);
  bp1->condition = g_strdup (bp2->condition);

  g_free (bp1->commands);
  bp1->commands = g_strdup (bp2->commands);
}


mcgdb_bp *
mcgdb_bp_copy (const mcgdb_bp * bp) {
  mcgdb_bp * bp_new = g_new (mcgdb_bp, 1);
  mcgdb_bp_copy_to (bp,bp_new);
  return bp_new;
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


void
insert_bp_to_list (mcgdb_bp *bp) {
  mcgdb_bps = g_list_append (mcgdb_bps, bp);
}

void pkg_bps_del(json_t *pkg) {
  /*executes on receive from gdb*/
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
    }
    else {
      number = myjson_int (bp_data, "number");
      bp = get_by_number (number);
    }
    message_assert (bp!=NULL);
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
  /*executes on receive from gdb*/
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
        /*this bp created and quickly deleted. wait next message that delete this breakpoint*/
        continue;
      }
    }
    else {
      tmp = json_object_get (bp_data,"number");
      if (tmp) {
        int number = json_integer_value (tmp);
        bp = get_by_number (number);
      }
      if (!bp) {
        /*bp created through gdb*/
        bp = mcgdb_bp_new ();
        message_assert (bp!=NULL);
        bp->number = myjson_int (bp_data,"number");
        tmp = json_object_get (bp_data,"temporary");
        if (tmp)
          bp->temporary = json_boolean_value (tmp);
        insert_bp_to_list (bp);
      }
    }

    bp->wait_status = BP_NOWAIT;

    if (bp->number==-1) {
      bp->number = myjson_int (bp_data, "number");
    }

    tmp = json_object_get (bp_data, "locations");
    if (tmp) {
      int size = json_array_size (tmp);
      mcgdb_bp_clear_locations (bp);
      for (int idx=0;idx<size;idx++) {
        json_t *loc = json_array_get (tmp, idx);
        mcgdb_bp_add_location (bp, myjson_str (loc,"filename"),myjson_int (loc, "line"));
      }
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

    tmp = json_object_get (bp_data,"thread");
    if (tmp) {
      if (json_is_null (tmp))
        bp->thread = -1;
      else
        bp->thread = json_integer_value (tmp);
    }

    bp->hit_count = myjson_int (bp_data, "hit_count");

    tmp = json_object_get (bp_data,"condition");
    if (tmp) {
      if (bp->condition)
        g_free (bp->condition);
      if (json_is_null (tmp))
        bp->condition = NULL;
      else
        bp->condition = strdup (json_string_value (tmp));
    }

    tmp = json_object_get (bp_data,"commands");
    if (tmp) {
      if (bp->commands)
        g_free (bp->commands);
      if (json_is_null (tmp))
        bp->commands = NULL;
      else
        bp->commands = strdup (json_string_value (tmp));
    }
  }
}





