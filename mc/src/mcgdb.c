#include <sys/socket.h>
#include <netinet/in.h>
#include <sys/types.h>
#include <arpa/inet.h>
#include <config.h>
#include <stdlib.h>
#include <stdio.h>



//#include "src/editor/edit.h"
#include "lib/global.h"
#include "src/editor/edit-impl.h"
#include "lib/tty/tty-slang.h"
#include "lib/tty/key.h"
#include "lib/skin.h"
#include "src/editor/editwidget.h"
#include "lib/widget/mouse.h"
#include "src/editor/edit.h"

#include "src/mcgdb.h"
#include "src/mcgdb-bp.h"

#define STREQ(s1,s2) (!strncmp(s1,s2,strlen(s2)))

int mcgdb_listen_port;
int gdb_input_fd;
static GList * mcgdb_event_queue;

gboolean read_gdb_events;

enum window_type mcgdb_wtype; /*temporary unused*/


static void
read_bytes_from_gdb(char *buf, char stop_char, size_t size);

static void
parse_action_from_gdb(struct gdb_action * act);

static int
process_action_from_gdb(WEdit * h, struct gdb_action * act);

static enum window_type
get_win_type(const char * buf);

static enum gdb_cmd
get_command_num(const char *command);

void
mcgdb_error(void) {
  abort();
}

void
mcgdb_exit(void) {
  exit(0);
}

static enum window_type
get_win_type(const char * buf) {
  if(      STREQ(buf,"mcgdb_main_window") ) {
    return MCGDB_MAIN_WINDOW;
  }
  else if( STREQ(buf,"mcgdb_source_window") ) {
    return MCGDB_SOURCE_WINDOW;
  }
  else if( STREQ(buf,"mcgdb_backtrace_window") ) {
    return MCGDB_BACKTRACE_WINDOW;
  }
  else {
    return MCGDB_UNKNOWN_WINDOW_TYPE;
  }
}

int open_gdb_input_fd(void) {
  int sockfd;
  struct sockaddr_in serv_addr;
  char buf[100];
  enum gdb_cmd cmd;
  if(mcgdb_listen_port==0) {
    printf("you must specify `--gdb-port port`\n");
    mcgdb_exit();
  }
  sockfd = socket(AF_INET, SOCK_STREAM, 0);
  if (sockfd < 0) {
    perror("ERROR opening socket");
    mcgdb_exit();
  }
  memset(&serv_addr, 0, sizeof(serv_addr)); 
  serv_addr.sin_family=AF_INET;
  serv_addr.sin_addr.s_addr=inet_addr("127.0.0.1");
  serv_addr.sin_port=htons(mcgdb_listen_port);
  if( connect(sockfd,(struct sockaddr *)&serv_addr,sizeof(serv_addr)) < 0) {
    perror("ERROR connect");
    mcgdb_exit();
  }
  gdb_input_fd=sockfd;
  while (1) {
    bzero(buf,sizeof(buf));
    read_bytes_from_gdb(buf,':',sizeof(buf));
    cmd=get_command_num(buf);
    if(cmd!=MCGDB_SET_WINDOW_TYPE) {
      printf("bad command received: `%s`\n",buf);
      read_bytes_from_gdb(buf,';',sizeof(buf));
      continue;
    }
    else {
      read_bytes_from_gdb(buf,';',sizeof(buf));
      mcgdb_wtype=get_win_type(buf);
      if(mcgdb_wtype==MCGDB_UNKNOWN_WINDOW_TYPE) {
        printf("unknown window type `%s`\n",buf);
        continue;
      }
      else {
        /*OK*/
        break;
      }
    }
  }
  return sockfd;
}



static void
read_bytes_from_gdb(char *buf, char stop_char, size_t size) {
  int rc;
  size_t l=0;
  while(1) {
    if(l==size-1) {
      *buf=0;
      return;
    }
    rc=read(gdb_input_fd,buf,1);
    if(rc<=0) {
      if(errno==EINTR) {
        continue;
      }
      else {
        perror("read");
        mcgdb_exit();
      }
    }
    if( (*buf)==stop_char ) {
      *buf=0;
      return;
    }
    l++;
    buf++;
  }
}

static enum gdb_cmd
get_command_num(const char *command) {
# define compare_cmd(CMD) (!strncmp(command,(CMD),strlen( (CMD) )))
  if(      compare_cmd("mark") ) {
    return MCGDB_MARK;
  }
  else if( compare_cmd("unmark_all") ) {
    return MCGDB_UNMARK_ALL;
  }
  else if( compare_cmd("unmark") ) {
    return MCGDB_UNMARK;
  }
  else if( compare_cmd("goto") ) {
    return MCGDB_GOTO;
  }
  else if( compare_cmd("fopen") ) {
    return MCGDB_FOPEN;
  }
  else if( compare_cmd("fclose") ) {
    return MCGDB_FCLOSE;
  }
  else if( compare_cmd("show_line_numbers") ) {
    return MCGDB_SHOW_LINE_NUMBERS;
  }
  else if( compare_cmd("set_window_type") ) {
    return MCGDB_SET_WINDOW_TYPE;
  }
  else if( compare_cmd("remove_bp_all") ) {
    return MCGDB_BP_REMOVE_ALL;
  }
  else if( compare_cmd("insert_bp") ) {
    return MCGDB_BP_INSERT;
  }
  else if( compare_cmd("remove_bp") ) {
    return MCGDB_BP_REMOVE;
  }
  else {
    return MCGDB_UNKNOWN;
  }
}

static void
parse_action_from_gdb(struct gdb_action * act) {
  // command:arg;
  // mark:lineno;
  // unmark:lineno;
  // goto:lineno;
  // fopen:filename;
  static char command[512],argstr[512];
  enum gdb_cmd cmd;
  read_bytes_from_gdb(command,':',sizeof(command));
  cmd=get_command_num(command);
  act->command=cmd;
  switch(cmd) {
    case MCGDB_MARK:
    case MCGDB_UNMARK:
    case MCGDB_GOTO:
    case MCGDB_BP_REMOVE:
    case MCGDB_BP_INSERT:
      read_bytes_from_gdb(argstr,';',sizeof(argstr));
      act->line=atoi(argstr);
      break;
    case MCGDB_FOPEN:
      read_bytes_from_gdb(argstr,',',sizeof(argstr));
      act->filename=strdup(argstr);
      read_bytes_from_gdb(argstr,';',sizeof(argstr));
      act->line=atoi(argstr);
      break;
    default:
      read_bytes_from_gdb(argstr,';',sizeof(argstr));/*remove ';' from stream*/
  }
}

static int
process_action_from_gdb(WEdit * edit, struct gdb_action * act) {
  //int alt0;
  //Widget *wh;
  //edit->force |= REDRAW_COMPLETELY;
  switch(act->command) {
    case MCGDB_MARK:
      book_mark_insert( edit, act->line, BOOK_MARK_COLOR);
      break;
    case MCGDB_UNMARK:
      book_mark_clear( edit, act->line, BOOK_MARK_COLOR);
      break;
    case MCGDB_UNMARK_ALL:
      book_mark_flush( edit, -1);
      break;
    case MCGDB_BP_INSERT:
      mcgdb_bp_insert (act->line);
      break;
    case MCGDB_BP_REMOVE:
      mcgdb_bp_remove (act->line);
      break;
    case MCGDB_BP_REMOVE_ALL:
      mcgdb_bp_remove_all ();
      break;
    case MCGDB_FOPEN:
      edit_file(vfs_path_build_filename(act->filename, (char *) NULL),act->line);
      //TODO нужно ли очищать vfs_path ?
      break;
    case MCGDB_FCLOSE:
//      alt0=KEY_F(10);
//      dlg_process_event (h, alt0, 0);
//      wh = WIDGET (h);
//      if (widget_get_state (wh, WST_CLOSED))
//        send_message (h, NULL, MSG_VALIDATE, 0, NULL);
      return MCGDB_EXIT_DLG;
    case MCGDB_SHOW_LINE_NUMBERS:
      //edit_set_show_numbers_cmd(h);
      option_line_state=1;
      break;
    case MCGDB_GOTO:
      edit_move_display (edit, act->line - WIDGET (edit)->lines / 2 - 1);
      edit_move_to_line (edit, act->line);
      break;
    default:
      break;
  }
  return MCGDB_OK;
}

int
mcgdb_action_from_gdb(WEdit * edit) {
  struct gdb_action act;
  parse_action_from_gdb(&act);
  return process_action_from_gdb(edit,&act);
}

static const char *
stringify_click_type(mouse_event_t * event) {
  static char buf[512];
  size_t len=0;
  buf[0]=0;
# define APPEND_EVT(EVT)  if( event->msg==EVT ) { len+=sprintf(buf+len, #EVT "|"); }
  /*
  APPEND_EVT(GPM_MOVE);
  APPEND_EVT(GPM_DRAG);
  APPEND_EVT(GPM_DOWN);
  APPEND_EVT(GPM_UP);
  APPEND_EVT(GPM_SINGLE);
  APPEND_EVT(GPM_DOUBLE);
  APPEND_EVT(GPM_TRIPLE);
  APPEND_EVT(GPM_MFLAG);
  APPEND_EVT(GPM_HARD);*/
  APPEND_EVT(MSG_MOUSE_NONE);
  APPEND_EVT(MSG_MOUSE_DOWN);
  APPEND_EVT(MSG_MOUSE_UP);
  APPEND_EVT(MSG_MOUSE_CLICK);
  APPEND_EVT(MSG_MOUSE_DRAG);
  APPEND_EVT(MSG_MOUSE_MOVE);
  APPEND_EVT(MSG_MOUSE_SCROLL_UP);
  APPEND_EVT(MSG_MOUSE_SCROLL_DOWN);
# undef APPEND_EVT
  buf[len-1]=0;
  return buf;
}

void
mcgdb_send_mouse_event_to_gdb(WEdit * edit, mouse_event_t * event) {
  static char lb[512];
  const char * filename;
  if(!edit)
    return;
  filename = edit_get_file_name(edit);
  sprintf(lb,"mouse_click:%s,%li,%li,%s;",
    filename?filename:"",
    event->x     - edit->start_col,
    event->y + 1 + edit->start_line,
    stringify_click_type(event));
  write_all(gdb_input_fd,lb,strlen(lb));
}

gboolean
mcgdb_ignore_mouse_event(WEdit * edit, mouse_event_t * event) {
  long cur_col;
  if(!edit)
    return FALSE;
  cur_col=event->x -1 - edit->start_col;
  if( cur_col <= 7 ) { //TODO 7 заменить константой-define шириной нумерного столбца
    return TRUE;
  }
  return FALSE;
}

void
mcgdb_queue_append_event(void) {
  struct gdb_action * gdb_evt = g_new0(struct gdb_action, 1);
  parse_action_from_gdb(gdb_evt);
  mcgdb_event_queue = g_list_append (mcgdb_event_queue, gdb_evt);
}

static void
free_gdb_evt (struct gdb_action * gdb_evt) {
  if( gdb_evt->filename )
    free(gdb_evt->filename);
  g_free(gdb_evt);
}

static gboolean
evt_convertable_to_key(struct gdb_action * gdb_evt) {
  switch(gdb_evt->command) {
    case MCGDB_FCLOSE:
      return TRUE;
    default:
      return FALSE;
  }
}

gboolean
mcgdb_queue_head_convertable_to_key(void) {
  if (!mcgdb_event_queue)
    return FALSE;
  return evt_convertable_to_key(mcgdb_event_queue->data);
}

int
mcgdb_queue_convert_head_to_key(void) {
  GList *l;
  struct gdb_action * gdb_evt;
  int d_key;
  l=mcgdb_event_queue;
  mcgdb_event_queue = g_list_remove_link (mcgdb_event_queue,l);
  gdb_evt=l->data;
  switch( gdb_evt->command ) {
    case MCGDB_FCLOSE:
      d_key=KEY_F(10);
      break;
//    case MCGDB_SHOW_LINE_NUMBERS:
//      d_key=ALT('n');
//      break;
    default:
      abort();
  }
  g_list_free(l);
  free_gdb_evt(gdb_evt);
  return d_key;
}

int
mcgdb_queue_process_event(WEdit * edit) {
  struct gdb_action * gdb_evt;
  int res=MCGDB_OK;
  GList *l;
  enum gdb_cmd cmd;

  if( !mcgdb_event_queue || !edit ) {
    return MCGDB_OK;
  }

  while(TRUE) {
    l=mcgdb_event_queue;
    if(!l)
      break;
    gdb_evt = l->data;
    cmd=gdb_evt->command;
    mcgdb_event_queue = g_list_remove_link (mcgdb_event_queue,l);
    g_list_free(l);
    process_action_from_gdb (edit,gdb_evt);
    free_gdb_evt (gdb_evt);
    if(cmd==MCGDB_FCLOSE) {
      return MCGDB_EXIT_DLG;
    }
    l=mcgdb_event_queue;
  }
  return res;
}

gboolean
mcgdb_queue_is_empty(void) {
  return mcgdb_event_queue==NULL;
}



void mcgdb_checkset_read_gdb_events(WDialog * h) {
  read_gdb_events=find_editor( h )!=0;
}


