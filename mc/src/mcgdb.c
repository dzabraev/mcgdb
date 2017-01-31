#ifndef _GNU_SOURCE
#   define _GNU_SOURCE 1
#endif
#include <stdio.h>

#include <sys/socket.h>
#include <netinet/in.h>
#include <sys/types.h>
#include <arpa/inet.h>
#include <config.h>
#include <stdlib.h>
#include <assert.h>


//#include "src/editor/edit.h"
#include "lib/global.h"
#include "src/editor/edit-impl.h"
#include "lib/tty/tty-slang.h"
#include "lib/tty/key.h"
#include "lib/skin.h"
#include "src/editor/editwidget.h"
#include "lib/widget/mouse.h"
#include "src/editor/edit.h"
#include "lib/tty/color.h"

#include "src/mcgdb.h"
#include "src/mcgdb-bp.h"

#include <jansson.h>

#define STREQ(s1,s2) (!strncmp(s1,s2,strlen(s2)))

int mcgdb_listen_port;
int gdb_input_fd;
static GList * mcgdb_event_queue;

gboolean read_gdb_events;


int mcgdb_current_line_color;
long mcgdb_curline; /*current execution line number*/

enum window_type mcgdb_wtype; /*temporary unused*/


static json_t *
read_pkg_from_gdb (void);

static void
sed_pkg_to_gdb (const char *msg);

static void
parse_action_from_gdb(struct gdb_action * act);

static int
process_action_from_gdb(WEdit * h, struct gdb_action * act);

static enum window_type
get_window_type(json_t * pkg);

static enum gdb_cmd
get_command_num(json_t * pkg);

void
mcgdb_error(void) {
  abort();
}

void
mcgdb_exit(void) {
  exit(0);
}

static enum window_type
get_window_type(json_t *pkg) {
  json_t *val;
  enum window_type type;
  const char *buf;

  val = json_object_get(pkg,"type");
  if (!json_is_string(val)) {
    type=MCGDB_UNKNOWN_WINDOW_TYPE;
  }
  else {
    buf=json_string_value(val);
    if(      STREQ(buf,"main_window") ) {
      type = MCGDB_MAIN_WINDOW;
    }
    else if( STREQ(buf,"source_window") ) {
      type = MCGDB_SOURCE_WINDOW;
    }
    else if( STREQ(buf,"backtrace_window") ) {
      type = MCGDB_BACKTRACE_WINDOW;
    }
    else {
      type = MCGDB_UNKNOWN_WINDOW_TYPE;
    }
  }

  json_decref(val);
  return type;
}

int
open_gdb_input_fd (void) {
  int sockfd;
  struct sockaddr_in serv_addr;
  char buf[100];
  json_t *pkg;

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
    while (1) {
      /*читаем пакет до тех пор, пока не придет нажный*/
      pkg = read_pkg_from_gdb();
      if (get_command_num(pkg)==MCGDB_SET_WINDOW_TYPE) {
        break;
      }
      else {
        char *msg=json_dumps(pkg,0);
        printf("bad command received: `%s`\n",msg);
        free(msg);
        json_decref(pkg);
      }
    }
    /*нужный пакет принят*/
    mcgdb_wtype = get_window_type(pkg);
    if (mcgdb_wtype==MCGDB_UNKNOWN_WINDOW_TYPE) {
        printf("unknown window type `%s`\n",buf);
    }
    else {
      break;
    }
    json_decref(pkg);
  }
  json_decref(pkg);
  return sockfd;
}

static void
sed_pkg_to_gdb (const char *msg) {
  size_t len=strlen(msg);
  char *s;
  asprintf(&s,"%zu;",len);
  write_all(gdb_input_fd,s,strlen(s));
  write_all(gdb_input_fd,msg,strlen(msg));
  free(s);
}

static json_t *
read_pkg_from_gdb (void) {
  int rc;
  size_t bufsize=1024, N, n=0;
  json_error_t error;
  json_t *pkg;

  char * buf = malloc(bufsize), *p=buf;
  if(!buf)
    return NULL;
  //message have following structure: len;data
  //first read len
  while(1) {
    assert(n<bufsize);
    rc=read(gdb_input_fd,p,1);
    if(rc<=0) {
      if(errno==EINTR) {
        continue;
      }
      else {
        mcgdb_exit();
      }
    }
    if(*p==';')
      break;
    p++;
    n++;
  }
  *p=0;
  N=atoi(buf);
  if(bufsize<N+1) {
    bufsize=N+1;
    buf = realloc(buf, bufsize);
    if (!buf)
      mcgdb_exit();
  }
  n=0;
  p=buf;
  while(n<N) {
    rc=read(gdb_input_fd,p,N-n);
    if(rc<=0) {
      if(errno==EINTR) {
        continue;
      }
      else {
        mcgdb_exit();
      }
    }
    n+=rc;
    p+=rc;
  }
  *p=0;
  pkg = json_loads(buf, 0, &error);
  free(buf);
  return pkg;

}

static enum gdb_cmd
get_command_num(json_t *pkg) {
  json_t * val;
  const char *command;
  enum gdb_cmd cmd;

  val = json_object_get(pkg,"cmd");
  if (!json_is_string(val)) {
    cmd= MCGDB_ERROR;
  }
  else {
    command = json_string_value(val);
#   define compare_cmd(CMD) (!strncmp(command,(CMD),strlen( (CMD) )))
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
    else if( compare_cmd("set_window_type") ) {
      return MCGDB_SET_WINDOW_TYPE;
    }
    else if( compare_cmd("remove_bp_all") ) {
      return MCGDB_BP_REMOVE_ALL;
    }
    else if( compare_cmd("insert_bps") ) {
      return MCGDB_BPS_INSERT;
    }
    else if( compare_cmd("insert_bp") ) {
      return MCGDB_BP_INSERT;
    }
    else if( compare_cmd("remove_bp") ) {
      return MCGDB_BP_REMOVE;
    }
    else if( compare_cmd("color_curline")) {
      return MCGDB_COLOR_CURLINE;
    }
    else if (compare_cmd("set_curline")) {
      return MCGDB_SET_CURLINE;
    }
    else {
      return MCGDB_UNKNOWN;
    }
  }
  json_decref(val);
  return cmd;
}

#define EXTRACT_FIELD_LONG(root,field) do{\
  json_t *rootval;\
  rootval = json_object_get(root,#field);\
  if (!json_is_integer(rootval)) {\
    act->command = MCGDB_ERROR;\
    json_decref(rootval);\
    return;\
  }\
  act->field = (long)json_integer_value(rootval);\
  json_decref(rootval);\
}while(0)


#define EXTRACT_FIELD_STR(root,field) do{\
  json_t *rootval;\
  rootval = json_object_get(root,#field);\
  if (!json_is_string(rootval)) {\
    act->command = MCGDB_ERROR;\
    json_decref(rootval);\
    return;\
  }\
  act->field = strdup(json_string_value(rootval));\
  json_decref(rootval);\
}while(0)


static void
parse_action_from_gdb(struct gdb_action * act) {
  // command:arg;
  // mark:lineno;
  // unmark:lineno;
  // goto:lineno;
  // fopen:filename;
  enum gdb_cmd cmd;
  json_t *pkg;
  pkg = read_pkg_from_gdb();
  if (!json_is_object(pkg)) {
    act->command = MCGDB_ERROR;
    json_decref(pkg);
    return;
  }
  cmd=get_command_num(pkg);
  act->command=cmd;
  act->pkg=pkg;
  switch(cmd) {
    case MCGDB_MARK:
    case MCGDB_UNMARK:
    case MCGDB_GOTO:
    case MCGDB_BPS_INSERT:
      break;
    case MCGDB_BP_REMOVE:
    case MCGDB_BP_INSERT:
      EXTRACT_FIELD_LONG(pkg,line);
      break;
    case MCGDB_FOPEN:
      EXTRACT_FIELD_LONG(pkg,line);
      EXTRACT_FIELD_STR(pkg,filename);
      break;
    case MCGDB_COLOR_CURLINE:
      EXTRACT_FIELD_STR(pkg,bgcolor);
      EXTRACT_FIELD_STR(pkg,tecolor);
      act->command=MCGDB_UNKNOWN; /*временная мера*/
      break;
    case MCGDB_SET_CURLINE:
      EXTRACT_FIELD_LONG(pkg,line);
      break;
    default:
      break;
  }
}


static int
process_action_from_gdb(WEdit * edit, struct gdb_action * act) {
  //int alt0;
  //Widget *wh;
  //edit->force |= REDRAW_COMPLETELY;
  json_t *j_lines,*j_line,*j_clear_old;
  switch(act->command) {
    case MCGDB_MARK:
      book_mark_insert( edit, act->line, mcgdb_current_line_color);
      break;
    case MCGDB_UNMARK:
      book_mark_clear( edit, act->line, mcgdb_current_line_color);
      break;
    case MCGDB_UNMARK_ALL:
      book_mark_flush( edit, -1);
      break;
    case MCGDB_BPS_INSERT:
      j_clear_old = json_object_get (act->pkg,"clear_old");
      if (j_clear_old) {
        int clear_old = json_boolean_value (j_clear_old);
        if (clear_old)
          mcgdb_bp_remove_all ();
      }
      j_lines = json_object_get (act->pkg,"bp_lines");
      if (j_lines) {
        size_t i;
        int line;
        for (i = 0; i < json_array_size (j_lines); i++) {
          j_line = json_array_get (j_lines, i);
          line = (long)json_integer_value (j_line);
          mcgdb_bp_insert (line);
        }
      }
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
      mcgdb_bp_remove_all ();
      if(mcgdb_curline>0)
        book_mark_clear (edit, mcgdb_curline, mcgdb_current_line_color);
      mcgdb_curline=act->line;
      edit_file(vfs_path_build_filename(act->filename, (char *) NULL),act->line); /*тут исполнение проваливается в эту функцию
      и не перейдет на след. строчку, пока edit-файла не закроется. Поэтому мы не может открыть файл, и сразу же подкрасить
      текущую строку. Это надо делать следующим пакетом.*/
      //TODO нужно ли очищать vfs_path ?
      break;
    case MCGDB_FCLOSE:
      return MCGDB_EXIT_DLG;
    case MCGDB_GOTO:
      edit_move_display (edit, act->line - WIDGET (edit)->lines / 2 - 1);
      edit_move_to_line (edit, act->line);
      break;
    case MCGDB_COLOR_CURLINE:
      mcgdb_set_current_line_color(act->tecolor,act->bgcolor,NULL,edit);
      break;
    case MCGDB_SET_CURLINE:
      book_mark_clear (edit, mcgdb_curline, mcgdb_current_line_color);
      mcgdb_curline=act->line;
      book_mark_insert (edit, mcgdb_curline, mcgdb_current_line_color);
      edit_move_display (edit, act->line - WIDGET (edit)->lines / 2 - 1);
      edit_move_to_line (edit, act->line);
      break;
    default:
      break;
  }
  return MCGDB_OK;
}

/*
static const char *
stringify_click_type(mouse_event_t * event) {
  static char buf[512];
  size_t len=0;
  buf[0]=0;
# define APPEND_EVT(EVT)  if( event->msg==EVT ) { len+=sprintf(buf+len, #EVT "|"); }
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
*/


void
mcgdb_send_mouse_event_to_gdb (WEdit * edit, mouse_event_t * event) {
  long click_col, click_line;
  char *pkg=0;
  if (!edit)
    return;
  click_col  = event->x     - edit->start_col;
  click_line = event->y + 1 + edit->start_line;
  if (event->msg==MSG_MOUSE_DOWN && click_col<=7) {
    asprintf (&pkg,"{\"cmd\":\"editor_breakpoint\",\"line\": %ld}",click_line);
  }
  if (pkg)
    sed_pkg_to_gdb (pkg);
    free (pkg);
  return;
/*
  filename = edit_get_file_name(edit);
  sprintf(lb,"mouse_click:%s,%li,%li,%s;",
    filename?filename:"",
    event->x     - edit->start_col,
    event->y + 1 + edit->start_line,
    stringify_click_type(event));
  write_all(gdb_input_fd,lb,strlen(lb));
*/
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
  if (gdb_evt->filename)
    free(gdb_evt->filename);
  if (gdb_evt->bgcolor)
    free(gdb_evt->bgcolor);
  if (gdb_evt->tecolor)
    free(gdb_evt->tecolor);
  if (gdb_evt->pkg)
    json_decref(gdb_evt->pkg);
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


int
mcgdb_permissible_key(WEdit * e, int c) {
  /*При помощи данной функции достигается режим read-only для
   * write available окна
  */
  int ch,cmd;
  if (c==EV_MOUSE || c==EV_GDB_MESSAGE) {
    return 1;
  }
  edit_translate_key (e, c, &cmd, &ch);
  switch(cmd) {
    case CK_Up:
    case CK_Down:
    case CK_Left:
    case CK_Right:
    case CK_Home:
    case CK_End:
    case CK_LeftQuick:
    case CK_RightQuick:
    case CK_PageUp:
    case CK_PageDown:
    case CK_HalfPageUp:
    case CK_HalfPageDown:
    case CK_Top:
    case CK_Bottom:
    case CK_TopOnScreen:
    case CK_MiddleOnScreen:
    case CK_BottomOnScreen:
    case CK_WordLeft:
    case CK_WordRight:
    case CK_Search:
    case CK_SearchContinue:
    case CK_Shell:
    case CK_SelectCodepage:
    case CK_Goto:
    case CK_Find:
    case CK_ScrollUp:
    case CK_ScrollDown:
    case CK_ParagraphUp:
    case CK_ParagraphDown:
    /* bookmarks */
    case CK_Bookmark:
    case CK_BookmarkFlush:
    case CK_BookmarkNext:
    case CK_BookmarkPrev:
    /* mark commands */
    case CK_MarkLeft:
    case CK_MarkRight:
    case CK_MarkUp:
    case CK_MarkDown:
    case CK_MarkToWordBegin:
    case CK_MarkToWordEnd:
    case CK_MarkToHome:
    case CK_MarkToEnd:

    case CK_MarkColumn:
    case CK_MarkWord:
    case CK_MarkLine:
    case CK_MarkAll:
    case CK_Unmark:
    case CK_MarkPageUp:
    case CK_MarkPageDown:
    case CK_MarkToFileBegin:
    case CK_MarkToFileEnd:
    case CK_MarkToPageBegin:
    case CK_MarkToPageEnd:
    case CK_MarkScrollUp:
    case CK_MarkScrollDown:
    case CK_MarkParagraphUp:
    case CK_MarkParagraphDown:
    /* column mark commands */
    case CK_MarkColumnPageUp:
    case CK_MarkColumnPageDown:
    case CK_MarkColumnLeft:
    case CK_MarkColumnRight:
    case CK_MarkColumnUp:
    case CK_MarkColumnDown:
    case CK_MarkColumnScrollUp:
    case CK_MarkColumnScrollDown:
    case CK_MarkColumnParagraphUp:
    case CK_MarkColumnParagraphDown:
    /* block commands */
    case CK_BlockSave:
    case CK_BlockShiftLeft:
    case CK_BlockShiftRight:
    case CK_DeleteLine:
    case CK_MatchBracket:
    //case CK_About,
    case CK_ShowMargin:
    case CK_ShowTabTws:
    case CK_SyntaxOnOff:
    case CK_SyntaxChoose:
    /* mcgdb */
    case CK_MCGDB_Breakpoint:
    case CK_MCGDB_DE_Breakpoint:
    case CK_MCGDB_Goto_ELine:
    case CK_MCGDB_Next:
    case CK_MCGDB_Step:
    case CK_MCGDB_Until:
    case CK_MCGDB_Continue:
    case CK_MCGDB_Print:
      return 1;
    default:
      return 0;
  }


}

void
mcgdb_set_current_line_color(
  const char *fgcolor /*color of text*/,
  const char *bgcolor /*color of background*/,
  const char *attrs, WEdit * edit ) {
  if (edit && mcgdb_curline>=0)
    book_mark_clear (edit, mcgdb_curline, mcgdb_current_line_color);
  mcgdb_current_line_color = tty_try_alloc_color_pair2 (fgcolor, bgcolor, attrs, FALSE);
  if (edit && mcgdb_curline>=0)
    book_mark_insert (edit, mcgdb_curline, mcgdb_current_line_color);
}

void
mcgdb_init(void) {
  mcgdb_curline=-1;
  mcgdb_set_current_line_color("red","black",NULL,NULL);
  option_line_state=1;
}


void
mcgdb_cmd_breakpoint (WEdit * e) {
  char *pkg;
  long curline = e->buffer.curs_line+1;
  asprintf (&pkg,"{\"cmd\":\"editor_breakpoint\",\"line\": %ld}",curline);
  sed_pkg_to_gdb (pkg);
  free (pkg);
}

void
mcgdb_cmd_disableenable_bp (WEdit * e) {
  char *pkg;
  long curline = e->buffer.curs_line+1;
  asprintf (&pkg,"{\"cmd\":\"editor_breakpoint_de\",\"line\": %ld}",curline);
  sed_pkg_to_gdb (pkg);
  free (pkg);
}

void
mcgdb_cmd_goto_eline (void) {

}

void
mcgdb_cmd_next(void) {
  sed_pkg_to_gdb ("{\"cmd\":\"editor_next\"}");
}

void
mcgdb_cmd_step(void) {
  sed_pkg_to_gdb ("{\"cmd\":\"editor_step\"}");
}

void
mcgdb_cmd_until(void) {
  sed_pkg_to_gdb ("{\"cmd\":\"editor_until\"}");
}

void
mcgdb_cmd_continue(void) {
  sed_pkg_to_gdb ("{\"cmd\":\"editor_continue\"}");
}

void
mcgdb_cmd_print(void) {

}





