#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <stdlib.h>
#include "lib/widget.h"

enum gdb_cmd {
  MCGDB_UNKNOWN=0,
  MCGDB_MARK,
  MCGDB_UNMARK,
  MCGDB_GOTO,
  MCGDB_FOPEN,
  MCGDB_FCLOSE,
  MCGDB_SHOW_LINE_NUMBERS,
  MCGDB_SET_WINDOW_TYPE,
  MCGDB_UNMARK_ALL,
  MCGDB_BP_REMOVE_ALL,
  MCGDB_BP_REMOVE,
  MCGDB_BP_INSERT,
  MCGDB_COLOR_CURLINE,
  MCGDB_SET_CURLINE,
};

enum window_type {
  MCGDB_UNKNOWN_WINDOW_TYPE=0,
  MCGDB_MAIN_WINDOW,
  MCGDB_SOURCE_WINDOW,
  MCGDB_BACKTRACE_WINDOW
};

#define MCGDB_OK 0
#define MCGDB_EXIT_DLG 1

extern gboolean read_gdb_events;
extern int mcgdb_current_line_color; /*color of current execute line*/
extern long mcgdb_curline;
struct mouse_event_t;

struct gdb_action {
  enum gdb_cmd command;
  int     line;
  char   *filename;
  char  **argv;
  int     argc;
};

void mcgdb_error(void);
void mcgdb_exit(void);

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

void mcgdb_queue_append_event(void);
int  mcgdb_queue_process_event(WEdit * edit);
gboolean mcgdb_ignore_mouse_event(WEdit * edit, mouse_event_t * event);
gboolean mcgdb_queue_is_empty(void);

int mcgdb_queue_convert_head_to_key(void);
gboolean mcgdb_queue_head_convertable_to_key(void);


void mcgdb_checkset_read_gdb_events(WDialog * h);

int mcgdb_permissible_key(int c);


void
mcgdb_set_current_line_color(
  const char *fgcolor /*color of text*/,
  const char *bgcolor /*color of background*/,
  const char *attrs , WEdit * edit);

void mcgdb_init(void);