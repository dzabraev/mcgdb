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
};

enum window_type {
  MCGDB_UNKNOWN_WINDOW_TYPE=0,
  MCGDB_MAIN_WINDOW,
  MCGDB_SOURCE_WINDOW
};

#define MCGDB_OK 0
#define MCGDB_EXIT_DLG 1



struct gdb_action {
  enum gdb_cmd command;
  int     line;
  char   *filename;
};

void mcgdb_error(void);

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

void mcgdb_send_mouse_event_to_gdb(WDialog * h, Gpm_Event * event);
int mcgdb_action_from_gdb(WDialog * h);

extern int      mcgdb_listen_port;
extern int      gdb_input_fd;


