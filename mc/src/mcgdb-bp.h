#ifndef __mcgdb_bp_h__
#define __mcgdb_bp_h__

extern int mcgdb_bp_color_wait_remove;
extern int mcgdb_bp_color_wait_insert;
extern int mcgdb_bp_color_normal;
extern int mcgdb_bp_color_disabled;

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
  long line;
  char *filename;
  int id;
  int number; /**gdb id of breakpoint*/

  bpwait wait_status;
} mcgdb_bp;


void            mcgdb_bp_module_init(void);
void            mcgdb_bp_module_free(void);
void            mcgdb_bp_remove_all(void);


mcgdb_bp*       mcgdb_bp_get    (const char *filename, long line); /*return mcgdb_bp if at line `line` exists breakpoint, else NULL*/
gboolean        mcgdb_bp_remove (const char *filename, long line);

int     mcgdb_bp_color  (const char *filename, long line); /*return color for drawing*/

gboolean
mcgdb_bp_process_click(const char *filename, long line, gboolean ask_cond);

void mcgdb_bp_insert (const char * filename, long line, bpwait wait, char * condition, gboolean disabled);
void mcgdb_bp_toggle_disable (const char * filename, long line);

void pkg_bps_upd(json_t *pkg);
void pkg_bps_del(json_t *pkg);



#endif