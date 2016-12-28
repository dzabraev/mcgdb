#include <config.h>
#include <stdlib.h>
#include <stdio.h>


#include "lib/global.h"
#include "src/mcgdb-bp.h"

typedef struct mcgdb_bp{
  long line;
} mcgdb_bp;

static GList * mcgdb_bps;

#define MCGDB_BP(l) ((mcgdb_bp *)(l->data))

void mcgdb_bp_init(void) {
}

void mcgdb_bp_free(void) {
  if(mcgdb_bps) {
    mcgdb_bp_remove_all();
    mcgdb_bps=0;
  }
}

int mcgdb_bp_exists(long line) {
  GList *l;
  if(!mcgdb_bps)
    return 0;
  for(l=mcgdb_bps;l!=NULL;l=l->next) {
    if( MCGDB_BP(l)->line==line ) {
      return 1;
    }
  }
  return 0;
}

void mcgdb_bp_insert(long line) {
  mcgdb_bp *bp;
  bp = g_new(mcgdb_bp, 1);
  bp->line=line;
  mcgdb_bps = g_list_append (mcgdb_bps,bp);
}

void mcgdb_bp_remove(long line) {
  GList *l;
  for(l=mcgdb_bps;l!=NULL;l=l->next) {
    if( MCGDB_BP(l)->line==line ) {
      mcgdb_bps = g_list_remove_link (mcgdb_bps, l);
      g_free (l->data);
      g_list_free (l);
      return;
    }
  }
}

void mcgdb_bp_remove_all(void) {
  if(!mcgdb_bps)
    return;
  g_list_free_full (mcgdb_bps,g_free);
  mcgdb_bps = 0;
}
