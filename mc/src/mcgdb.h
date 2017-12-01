#ifndef __mcgdb_h_
#define __mcgdb_h_



#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <stdlib.h>
#include "lib/widget.h"
#include <setjmp.h>
#include <jansson.h>

void __message_assert (const char *EX, const char *FILE, int LINE);

#define message_assert(EX) (void)((EX) || (__message_assert (#EX, __FILE__, __LINE__),0))

#define __json_extract(obj,field,extractor,checker) \
({\
  json_t *__tmp__ = json_object_get(obj,field);\
  message_assert(__tmp__!=NULL);\
  message_assert(checker(__tmp__));\
  extractor(__tmp__);\
})

#define __MCGDB_IDENTITY(x) x
//#define __MCGDB_CONSTTRUE_CHECKER(x) ((void *)1)

#define myjson_int(obj,field) __json_extract(obj,field,json_integer_value,json_is_integer)
#define myjson_str(obj,field) __json_extract(obj,field,json_string_value,json_is_string)
#define myjson_bool(obj,field) __json_extract(obj,field,json_boolean_value,json_is_boolean)
#define myjson_obj(obj,field) __json_extract(obj,field,__MCGDB_IDENTITY,json_is_object)
#define myjson_arr(obj,field) __json_extract(obj,field,__MCGDB_IDENTITY,json_is_array)




typedef enum gdb_cmd {
  MCGDB_UNKNOWN=0,
  MCGDB_ERROR_MESSAGE,
  MCGDB_NONE,

  /*editor widget*/
  MCGDB_ERROR,
  MCGDB_MARK,
  MCGDB_UNMARK,
  MCGDB_GOTO,
  MCGDB_FOPEN,
  MCGDB_FCLOSE,
  MCGDB_SET_WINDOW_TYPE,
  MCGDB_UNMARK_ALL,
  MCGDB_UPDATE_THREADS,
  MCGDB_BPSUPD,
  MCGDB_BPSDEL,
  MCGDB_SET_CURLINE,
  MCGDB_EXIT,
  MCGDB_INSERT_STR,

  /*common*/
  MCGDB_UPDATE_NODES,
  MCGDB_DO_ROW_VISIBLE,
  MCGDB_EXEMPLAR_CREATE,
  MCGDB_EXEMPLAR_DROP,
  MCGDB_EXEMPLAR_SET,
  MCGDB_EXEMPLAR_COPY,
  MCGDB_DROP_ROWS,
  MCGDB_DROP_NODES,
  MCGDB_TRANSACTION,
  MCGDB_INSERT_ROWS,
  MCGDB_CALL_CB,
} gdb_cmd_t;

enum window_type {
  MCGDB_UNKNOWN_WINDOW_TYPE=0,
  MCGDB_SRCWIN,
  MCGDB_AUXWIN,
  MCGDB_ASMWIN,
};

typedef enum  {
  MCGDB_OK=0,
  MCGDB_EXIT_DLG=1,
} mcgdb_rc;

extern gboolean disable_gdb_events;
extern gboolean read_gdb_events;
extern int mcgdb_current_line_color; /*color of current execute line*/
extern long mcgdb_curline;
struct mouse_event_t;
struct json_t;
extern enum window_type mcgdb_wtype;
extern struct gdb_action * event_from_gdb;
extern int selected_thread_global_num;
extern GList *thread_list;


typedef
struct gdb_action {
  enum gdb_cmd command;
  struct json_t *pkg;
} gdb_action_t;

void mcgdb_error(void);
void mcgdb_exit(void);
void mcgdb_exit_confirm(void);


static inline int write_all(int fd, const void *buf, size_t count)
{
	while (count) {
		ssize_t tmp;

		errno = 0;
		tmp = write(fd, buf, count);
		if (tmp > 0) {
			count -= tmp;
			if (count)
				buf = (void *) ((char *) buf + tmp);
		} else if (errno != EINTR && errno != EAGAIN)
			return -1;
		if (errno == EAGAIN)	/* Try later, *sigh* */
			usleep(250000);
	}
	return 0;
}

int  open_gdb_input_fd(void);
//void read_bytes_from_gdb(char *buf, char stop_char);
//void parse_action_from_gdb();
//int process_action_from_gdb(WDialog * h);
typedef struct WEdit WEdit;
void mcgdb_send_mouse_event_to_gdb(WEdit * edit, mouse_event_t * event);
//int mcgdb_action_from_gdb(WEdit * edit);

extern int	mcgdb_wait_gdb;
extern int      mcgdb_listen_port;
extern int      gdb_input_fd;

void mcgdb_checkset_read_gdb_events(WDialog * h);

int mcgdb_permissible_key(WEdit * e, int c);

gboolean mcgdb_available_key(int c);

void mcgdb_cmd_print(void);
void mcgdb_cmd_goto_eline (void);
void mcgdb_cmd_disableenable_bp (WEdit * e);
void mcgdb_cmd_breakpoint (WEdit * e);

void mcgdb_shellcmd(const char *cmd);

void        mcgdb_gdbevt_read (void);
gboolean    mcgdb_gdbevt_covertable_to_key (void);
int         mcgdb_gdbevt_covert_to_key (void);
int         mcgdb_gdbevt_process_edit (WEdit * edit);

extern jmp_buf mcgdb_jump_buf; /*for error processing*/

void free_gdb_evt (struct gdb_action * gdb_evt);

json_t *read_pkg_from_gdb (void);
void send_pkg_to_gdb (const char *msg);

gdb_cmd_t get_command_num(json_t *pkg);

enum {
  CALLBACK_SUCCESS=0,
  CALLBACK_ERROR=1,
};

typedef struct cbPair {
  void *err;
  void *succ;
  void *args;
} cbPair;

typedef struct {
  char *name;
  int num;
  int global_num;
  int pid;
  int tid;
  int lwp;
} thread_entry_t;

thread_entry_t * get_thread_by_global_num (int global_num);


int data_ptr_register (void *data);

gboolean mcgdb_src_dlg(void);

#endif /*__mcgdb_h_*/

