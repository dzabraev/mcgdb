#include <config.h>
#include <stdlib.h>
#include <stdio.h>


#include "lib/global.h"
#include "src/mcgdb-bp.h"

static GList * mcgdb_bps;

#define MCGDB_BP(l) ((mcgdb_bp *)(l->data))

int mcgdb_bp_color_wait_remove;
int mcgdb_bp_color_wait_insert;
int mcgdb_bp_color_normal;
int mcgdb_bp_color_disabled;


static void
mcgdb_bp_insert (long line, bptype type);


void
mcgdb_bp_init (void) {
}

void
mcgdb_bp_free (void) {
  if (mcgdb_bps) {
    mcgdb_bp_remove_all ();
    mcgdb_bps=0;
  }
}

mcgdb_bp *
mcgdb_bp_get (long line) {
  GList *l;
  if (!mcgdb_bps)
    return 0;
  for(l=mcgdb_bps;l!=NULL;l=l->next) {
    if( MCGDB_BP(l)->line==line ) {
      return MCGDB_BP(l);
    }
  }
  return NULL;
}

void
mcgdb_bp_insert (long line, bptype type) {
  mcgdb_bp *bp;
  bp = mcgdb_bp_get (line);
  if (bp) {
    /*at this line bp already exists, updete this*/
    bp->type=type;
  }
  else {
    bp = g_new (mcgdb_bp, 1);
    bp->line=line;
    bp->type=type;
    mcgdb_bps = g_list_append (mcgdb_bps,bp);
  }
}

void
mcgdb_bp_insert_normal (long line) {
  mcgdb_bp_insert (line, BP_NORMAL);
}

void
mcgdb_bp_insert_wait_remove (long line) {
  mcgdb_bp_insert (line, BP_WAIT_REMOVE);
}


void
mcgdb_bp_insert_wait_insert (long line) {
  mcgdb_bp_insert (line, BP_WAIT_INSERT);
}


void
mcgdb_bp_insert_disabled (long line) {
  mcgdb_bp_insert (line, BP_DISABLED);
}


void
mcgdb_bp_remove (long line) {
  GList *l;
  for(l=mcgdb_bps;l!=NULL;l=l->next) {
    if ( MCGDB_BP(l)->line==line ) {
      mcgdb_bps = g_list_remove_link (mcgdb_bps, l);
      g_free (l->data);
      g_list_free (l);
      return;
    }
  }
}

void
mcgdb_bp_remove_all (void) {
  if (!mcgdb_bps)
    return;
  g_list_free_full (mcgdb_bps,g_free);
  mcgdb_bps = 0;
}

int
mcgdb_bp_color(mcgdb_bp * bp) {
  switch(bp->type) {
    case BP_NORMAL:
      return mcgdb_bp_color_normal;
    case BP_DISABLED:
      return mcgdb_bp_color_disabled;
    case BP_WAIT_REMOVE:
      return mcgdb_bp_color_wait_remove;
    case BP_WAIT_INSERT:
      return mcgdb_bp_color_wait_insert;
    default:
      return mcgdb_bp_color_normal;
  }
}
