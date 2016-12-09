#ifndef __mcgdb_bp_h__
#define __mcgdb_bp_h__

int  mcgdb_bp_exists(long line); /*return TRUE if at line `row` exists breakpoint*/
void mcgdb_bp_insert(long line);
void mcgdb_bp_remove(long line);
void mcgdb_bp_remove_all(void);
void mcgdb_bp_init(void);
void mcgdb_bp_free(void);


#endif