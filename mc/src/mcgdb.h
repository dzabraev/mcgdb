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


enum gdb_cmd {
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
  MCGDB_BREAKPOINTS,
  MCGDB_COLOR,
  MCGDB_SET_CURLINE,
  MCGDB_EXIT,

  /*localwars widget*/
  MCGDB_LOCALVARS,
  MCGDB_BACKTRACE,
  MCGDB_REGISTERS,
  MCGDB_THREADS,
  MCGDB_TABLE_ASM,

};

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

extern gboolean read_gdb_events;
extern int mcgdb_current_line_color; /*color of current execute line*/
extern long mcgdb_curline;
struct mouse_event_t;
struct json_t;
extern enum window_type mcgdb_wtype;
extern struct gdb_action * event_from_gdb;

struct gdb_action {
  enum gdb_cmd command;
  struct json_t *pkg;
};

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

extern int      mcgdb_listen_port;
extern int      gdb_input_fd;

gboolean mcgdb_ignore_mouse_event(WEdit * edit, mouse_event_t * event);


void mcgdb_checkset_read_gdb_events(WDialog * h);

int mcgdb_permissible_key(WEdit * e, int c);


void
mcgdb_set_color (struct json_t * pkg, WEdit * edit);

void mcgdb_init(void);

gboolean mcgdb_available_key(int c);

void mcgdb_cmd_breakpoint(WEdit * e);
void mcgdb_cmd_disableenable_bp(WEdit * e);
void mcgdb_cmd_goto_eline(void);
void mcgdb_cmd_next(void);
void mcgdb_cmd_step(void);
void mcgdb_cmd_until(void);
void mcgdb_cmd_continue(void);
void mcgdb_cmd_print(void);
void mcgdb_cmd_frame_up(void);
void mcgdb_cmd_frame_down(void);
void mcgdb_cmd_finish(void);

void mcgdb_shellcmd(const char *cmd);

void        mcgdb_gdbevt_read (void);
gboolean    mcgdb_gdbevt_covertable_to_key (void);
int         mcgdb_gdbevt_covert_to_key (void);
int         mcgdb_gdbevt_process_edit (WEdit * edit);

extern jmp_buf mcgdb_jump_buf; /*for error processing*/

void free_gdb_evt (struct gdb_action * gdb_evt);

json_t *read_pkg_from_gdb (void);
void send_pkg_to_gdb (const char *msg);


#endif /*__mcgdb_h_*/

