#ifndef __mcgdb_bp_h__
#define __mcgdb_bp_h__

extern int mcgdb_bp_color_wait_remove;
extern int mcgdb_bp_color_wait_insert;
extern int mcgdb_bp_color_normal;
extern int mcgdb_bp_color_disabled;

typedef enum bptype {
  BP_NORMAL,
  BP_DISABLED,
  BP_WAIT_REMOVE,
  BP_WAIT_INSERT
} bptype;

typedef struct mcgdb_bp{
  long line;
  bptype type;
} mcgdb_bp;


mcgdb_bp*       mcgdb_bp_get(long line); /*return mcgdb_bp if at line `line` exists breakpoint, else NULL*/
void            mcgdb_bp_remove(long line);
void            mcgdb_bp_remove_all(void);
void            mcgdb_bp_init(void);
void            mcgdb_bp_free(void);
int             mcgdb_bp_color(mcgdb_bp * bp);

void mcgdb_bp_insert_normal      (long line);
void mcgdb_bp_insert_wait_remove (long line);
void mcgdb_bp_insert_wait_insert (long line);
void mcgdb_bp_insert_disabled    (long line);

#endif