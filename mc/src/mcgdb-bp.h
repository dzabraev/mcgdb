#ifndef __mcgdb_bp_h__
#define __mcgdb_bp_h__

extern int mcgdb_bp_color_wait_remove;
extern int mcgdb_bp_color_wait_insert;
extern int mcgdb_bp_color_normal;
extern int mcgdb_bp_color_disabled;

extern GList * mcgdb_bps;

typedef struct json_t json_t;

typedef enum bpwait {
  BP_NOWAIT,
  BP_WAIT_DELETE,
  BP_WAIT_UPDATE,
} bpwait;

typedef struct mcgdb_bp{
  gboolean enabled;
  gboolean silent;
  int ignore_count;
  int hit_count;
  gboolean temporary;
  int thread;
  char *condition;
  char *commands;
  int id;
  int number; /**gdb id of breakpoint*/
  GList *locations;
  char * create_loc; /*user input string for create location*/
  bpwait wait_status;
} mcgdb_bp;

#define MCGDB_BP(l) ((mcgdb_bp *)(l->data))


void            mcgdb_bp_module_init(void);
void            mcgdb_bp_module_free(void);
void            mcgdb_bp_remove_all(void);


mcgdb_bp*       mcgdb_bp_get    (const char *filename, long line); /*return mcgdb_bp if at line `line` exists breakpoint, else NULL*/

int     mcgdb_bp_color  (const char *filename, long line); /*return color for drawing*/

gboolean
mcgdb_bp_process_click(const char *filename, long line, gboolean ask_cond);

void mcgdb_bp_insert (const char * filename, long line, bpwait wait, char * condition, gboolean disabled);
void mcgdb_bp_toggle_disable (const char * filename, long line);
int count_bps (const char *filename, long line);
mcgdb_bp * mcgdb_bp_copy (const mcgdb_bp * bp);
void mcgdb_bp_copy_to (const mcgdb_bp * bp, mcgdb_bp * bp_new);
GList * mcgdb_bp_find_bp_with_location (GList *bpl, const char *filename, int line);
void mcgdb_bp_free (mcgdb_bp * bp);
mcgdb_bp * mcgdb_bp_new (void);




void pkg_bps_upd(json_t *pkg);
void pkg_bps_del(json_t *pkg);



#endif