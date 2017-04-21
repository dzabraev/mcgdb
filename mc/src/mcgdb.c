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
#include "lib/widget/mcgdb_lvarswidget.h"


#define STREQ(s1,s2) (!strncmp(s1,s2,strlen(s2)))

int mcgdb_listen_port;
int gdb_input_fd;

gboolean read_gdb_events;

int mcgdb_current_line_color;
long mcgdb_curline; /*current execution line number*/

enum window_type mcgdb_wtype;

struct gdb_action * event_from_gdb=NULL;

jmp_buf mcgdb_jump_buf;


static void
check_action_from_gdb(struct gdb_action * act);

int
process_action_from_gdb_edit(WEdit * edit, struct gdb_action * act);



static enum window_type
get_window_type(json_t * pkg);

static enum gdb_cmd
get_command_num(json_t * pkg);

static void
process_lines_array(json_t * j_lines,  void (*callback)(long) );

static gboolean
evt_convertable_to_key(struct gdb_action * gdb_evt);

void
mcgdb_error(void) {
  longjmp (mcgdb_jump_buf, 1);
}

void
mcgdb_exit(void) {
  longjmp (mcgdb_jump_buf, 1);
}

void
mcgdb_exit_confirm(void) {
  int ok;
  ok = (edit_query_dialog2 (_("Exit"), _("Exit from debug window?"), _("&Yes"), _("&Cancel")) == 0);
  if (ok)
    mcgdb_exit ();
  return;
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
    if(      STREQ(buf,"srcwin") ) {
      type = MCGDB_SRCWIN;
    }
    else if( STREQ(buf,"auxwin") ) {
      type = MCGDB_AUXWIN;
    }
    else if( STREQ(buf,"asmwin") ) {
      type = MCGDB_ASMWIN;
    }
    else {
      type = MCGDB_UNKNOWN_WINDOW_TYPE;
    }
  }

  return type;
}

int
open_gdb_input_fd (void) {
  /*  open socket and connect to gdb.
      initialize global variable |gdb_input_fd| 
  */
  int sockfd;
  struct sockaddr_in serv_addr;
  char buf[100];
  json_t *pkg;

  if(mcgdb_listen_port==0) {
    printf("you must specify `--gdb-port port`\n");
    return FALSE;
  }
  sockfd = socket(AF_INET, SOCK_STREAM, 0);
  if (sockfd < 0) {
    perror("ERROR opening socket");
    return FALSE;
  }
  memset(&serv_addr, 0, sizeof(serv_addr)); 
  serv_addr.sin_family=AF_INET;
  serv_addr.sin_addr.s_addr=inet_addr("127.0.0.1");
  serv_addr.sin_port=htons(mcgdb_listen_port);
  if( connect(sockfd,(struct sockaddr *)&serv_addr,sizeof(serv_addr)) < 0) {
    perror("ERROR connect");
    return FALSE;
  }
  gdb_input_fd=sockfd;
  while (1) {
    while (1) {
      /*читаем пакет до тех пор, пока не придет нужный*/
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
  return TRUE;
}

void
send_pkg_to_gdb (const char *msg) {
  size_t len=strlen(msg);
  char *s;
  asprintf(&s,"%zu;",len);
  write_all(gdb_input_fd,s,strlen(s));
  write_all(gdb_input_fd,msg,strlen(msg));
  free(s);
}

json_t *
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
    else if( compare_cmd("breakpoints") ) {
      return MCGDB_BREAKPOINTS;
    }
    else if( compare_cmd("color")) {
      return MCGDB_COLOR;
    }
    else if (compare_cmd("set_curline")) {
      return MCGDB_SET_CURLINE;
    }
    else if (compare_cmd("exit")) {
      return MCGDB_EXIT;
    }
    else if (compare_cmd("localvars")) {
      return MCGDB_LOCALVARS;
    }
    else if (compare_cmd("backtrace")) {
      return MCGDB_BACKTRACE;
    }
    else if (compare_cmd("registers")) {
      return MCGDB_REGISTERS;
    }
    else if (compare_cmd("threads")) {
      return MCGDB_THREADS;
    }
    else if (compare_cmd("error_message")) {
      return MCGDB_ERROR_MESSAGE;
    }
    else {
      return MCGDB_UNKNOWN;
    }
  }
  json_decref(val);
  return cmd;
}



static void
check_action_from_gdb(struct gdb_action * act) {
  enum gdb_cmd cmd;
  json_t *pkg;
  pkg = read_pkg_from_gdb();
  if (!json_is_object(pkg)) {
    act->command = MCGDB_ERROR;
    json_decref(pkg);
    return;
  }
  cmd=get_command_num(pkg);
  if (cmd==MCGDB_ERROR_MESSAGE) {
    edit_error_dialog("ERROR",json_string_value (json_object_get (pkg,"message")));
    act->command=MCGDB_NONE;
    act->pkg=NULL;
  }
  else {
    act->command=cmd;
    act->pkg=pkg;
  }
}

static void
process_lines_array(json_t * j_lines,  void (*callback)(long) ) {
  size_t i;
  int line;
  json_t *j_line;
  if (!j_lines)
    return;
  for (i = 0; i < json_array_size (j_lines); i++) {
    j_line = json_array_get (j_lines, i);
    line = (long)json_integer_value (j_line);
    callback (line);
  }
}

static void
pkg_breakpoints(json_t *pkg) {
  json_t *j_clear;
  j_clear = json_object_get (pkg,"clear");
  if (j_clear) {
    int clear = json_boolean_value (j_clear);
    if (clear)
      mcgdb_bp_remove_all ();
  }
  else {
    process_lines_array (json_object_get (pkg,"remove"), mcgdb_bp_remove);
  }
  process_lines_array (json_object_get (pkg,"normal"),      mcgdb_bp_insert_normal);
  process_lines_array (json_object_get (pkg,"wait_insert"), mcgdb_bp_insert_wait_insert);
  process_lines_array (json_object_get (pkg,"wait_remove"), mcgdb_bp_insert_wait_remove);
  process_lines_array (json_object_get (pkg,"disabled"),    mcgdb_bp_insert_disabled);
}

static void
pkg_fopen (json_t *pkg, WEdit * edit) {
  const char *filename;
  long line = (long)json_integer_value(json_object_get(pkg, "line"));
  filename = json_string_value(json_object_get(pkg, "filename"));
  mcgdb_bp_remove_all ();
  if(mcgdb_curline>0)
    book_mark_clear (edit, mcgdb_curline, mcgdb_current_line_color);
  mcgdb_curline=line;
  edit_file(vfs_path_build_filename(filename, (char *) NULL),line); /*тут исполнение проваливается в эту функцию
  и не перейдет на след. строчку, пока edit-файла не закроется. Поэтому мы не может открыть файл, и сразу же подкрасить
  текущую строку. Это надо делать следующим пакетом.*/
  //TODO нужно ли очищать vfs_path ?
}

static void
pkg_goto (json_t *pkg, WEdit * edit) {
  long line = (long)json_integer_value(json_object_get(pkg, "line"));
  edit_move_display (edit, line - WIDGET (edit)->lines / 2 - 1);
  edit_move_to_line (edit, line);
}

static void
pkg_mark (json_t *pkg, WEdit * edit) {
  long line = (long)json_integer_value(json_object_get(pkg, "line"));
  book_mark_insert( edit, line, mcgdb_current_line_color);
}

static void
pkg_unmark (json_t *pkg, WEdit * edit) {
  long line = (long)json_integer_value(json_object_get(pkg, "line"));
  book_mark_clear( edit, line, mcgdb_current_line_color);
}

static void
pkg_unmark_all (WEdit * edit) {
  book_mark_flush( edit, -1);
}


static void
pkg_color (json_t *pkg, WEdit * edit) {
  mcgdb_set_color(pkg,edit);
}

static void
pkg_set_curline (json_t *pkg, WEdit * edit) {
  long line = (long)json_integer_value(json_object_get(pkg, "line"));
  book_mark_clear (edit, mcgdb_curline, mcgdb_current_line_color);
  mcgdb_curline = line;
  book_mark_insert (edit, mcgdb_curline, mcgdb_current_line_color);
  edit_move_display (edit, line - WIDGET (edit)->lines / 2 - 1);
  edit_move_to_line (edit, line);
}


int
process_action_from_gdb_edit(WEdit * edit, struct gdb_action * act) {
  json_t *pkg=act->pkg;
  assert(act->command!=MCGDB_FCLOSE);
  switch(act->command) {
    case MCGDB_EXIT:
      mcgdb_exit ();
      break;
    case MCGDB_MARK:
      pkg_mark (pkg,edit);
      break;
    case MCGDB_UNMARK:
      pkg_unmark (pkg,edit);
      break;
    case MCGDB_UNMARK_ALL:
      pkg_unmark_all (edit);
      break;
    case MCGDB_BREAKPOINTS:
      pkg_breakpoints (pkg);
      break;
    case MCGDB_FOPEN:
      pkg_fopen (pkg,edit);
      break;
    case MCGDB_GOTO:
      pkg_goto (pkg,edit);
      break;
    case MCGDB_COLOR:
      pkg_color (pkg,edit);
      break;
    case MCGDB_SET_CURLINE:
      pkg_set_curline(pkg,edit);
      break;
    default:
      break;
  }
  return MCGDB_OK;
}


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
    send_pkg_to_gdb (pkg);
    free (pkg);
  return;
}

gboolean
mcgdb_ignore_mouse_event(WEdit * edit, mouse_event_t * event) {
  long cur_col;
  if(!edit)
    return FALSE;
  cur_col=event->x -1 - edit->start_col;
  if( cur_col <= 7 ) { //TODO семь заменить константой-define шириной нумерного столбца
    return TRUE;
  }
  return FALSE;
}

void
mcgdb_gdbevt_read (void) {
  assert (event_from_gdb==NULL);
  event_from_gdb = g_new0 (struct gdb_action, 1);
  check_action_from_gdb (event_from_gdb);
}

gboolean
mcgdb_gdbevt_covertable_to_key (void) {
  return evt_convertable_to_key(event_from_gdb);
}

int
mcgdb_gdbevt_covert_to_key (void) {
  int d_key;
  switch( event_from_gdb->command ) {
    case MCGDB_FCLOSE:
      d_key=KEY_F(19); /*this button will be translate into CK_Quit*/
      break;
    default:
      abort ();
  }
  free_gdb_evt (event_from_gdb);
  event_from_gdb=NULL;
  return d_key;
}




int
mcgdb_gdbevt_process_edit (WEdit * edit) {
  struct gdb_action * tmp = event_from_gdb;
  int rc;
  event_from_gdb=NULL;
  rc = process_action_from_gdb_edit (edit, tmp);
  free_gdb_evt (tmp);
  return rc;
}


void
free_gdb_evt (struct gdb_action * gdb_evt) {
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



void mcgdb_checkset_read_gdb_events(WDialog * h) {
  read_gdb_events = (find_editor (h)!=NULL) || is_mcgdb_aux_dialog(h);
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
    case CK_MCGDB_Exit:
    case CK_Quit:
    case CK_QuitQuiet:
    case CK_Close: /*
    * Обязательно надо добавлять эти действия,
    * иначе мы не сможем закрыть файл даже программно
    * и стек будет увеличиваться при открытии каждого файла
    */
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
        /* file commands */
    case CK_EditSyntaxFile:
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
    case CK_MCGDB_Frame_up:
    case CK_MCGDB_Frame_down:
    case CK_MCGDB_Finish:
      return 1;
    default:
      return 0;
  }


}

static void
extract_color( json_t *color, const char **text_color,
    const char **bg_color, const char **attrs) {
  json_t *j_attrs;
  *text_color = json_string_value (json_object_get (color, "text_color"));
  *bg_color = json_string_value (json_object_get (color, "background_color"));
  j_attrs = json_object_get (color, "attrs");
  *attrs = j_attrs ? json_string_value (j_attrs) : NULL;
}

#define SET_COLOR_BP(pkg,type) do {\
  json_t * color_bp = json_object_get (pkg, "color_bp_" #type); \
  if (color_bp) { \
    const char *text_color, *bg_color, *attrs; \
    extract_color(color_bp, &text_color, &bg_color, &attrs); \
    mcgdb_bp_color_ ## type  = tty_try_alloc_color_pair2 (text_color, bg_color, attrs, FALSE); \
  } \
} while(0)\

void
mcgdb_set_color (json_t * pkg, WEdit * edit) {
  json_t *color_curline;
  color_curline = json_object_get (pkg, "color_curline");
  if (color_curline) {
    const char *text_color, *bg_color, *attrs;
    extract_color(color_curline, &text_color, &bg_color, &attrs);
    if (edit && mcgdb_curline>=0)
      book_mark_clear (edit, mcgdb_curline, mcgdb_current_line_color);
    mcgdb_current_line_color = tty_try_alloc_color_pair2 (text_color, bg_color, attrs, FALSE);
    if (edit && mcgdb_curline>=0)
      book_mark_insert (edit, mcgdb_curline, mcgdb_current_line_color);
  }
  SET_COLOR_BP(pkg,normal);
  SET_COLOR_BP(pkg,disabled);
  SET_COLOR_BP(pkg,wait_remove);
  SET_COLOR_BP(pkg,wait_insert);
  edit->force |= REDRAW_COMPLETELY;
}

void
mcgdb_init(void) {
  mcgdb_curline=-1;
  mcgdb_current_line_color   = tty_try_alloc_color_pair2 ("red", "black",   "bold", FALSE);
  mcgdb_bp_color_normal      = tty_try_alloc_color_pair2 ("red", "black",   NULL, FALSE);
  mcgdb_bp_color_disabled    = tty_try_alloc_color_pair2 ("red", "wite",    NULL, FALSE);
  mcgdb_bp_color_wait_insert = tty_try_alloc_color_pair2 ("red", "yellow",  NULL, FALSE);
  mcgdb_bp_color_wait_remove = tty_try_alloc_color_pair2 ("red", "magenta", NULL, FALSE);
  option_line_state=1;
}


void
mcgdb_cmd_breakpoint (WEdit * e) {
  char *pkg;
  long curline = e->buffer.curs_line+1;
  asprintf (&pkg,"{\"cmd\":\"editor_breakpoint\",\"line\": %ld}",curline);
  send_pkg_to_gdb (pkg);
  free (pkg);
}

void
mcgdb_cmd_disableenable_bp (WEdit * e) {
  char *pkg;
  long curline = e->buffer.curs_line+1;
  asprintf (&pkg,"{\"cmd\":\"editor_breakpoint_de\",\"line\": %ld}",curline);
  send_pkg_to_gdb (pkg);
  free (pkg);
}

void
mcgdb_cmd_goto_eline (void) {

}

gboolean
mcgdb_available_key (int c) {
  switch (c) {
    //case KEY_F(10):
    //  return FALSE;
    default:
      return TRUE;
  }
}

void
mcgdb_cmd_next(void) {
  send_pkg_to_gdb ("{\"cmd\":\"editor_next\"}");
}

void
mcgdb_cmd_step(void) {
  send_pkg_to_gdb ("{\"cmd\":\"editor_step\"}");
}

void
mcgdb_cmd_until(void) {
  send_pkg_to_gdb ("{\"cmd\":\"editor_until\"}");
}

void
mcgdb_cmd_continue(void) {
  send_pkg_to_gdb ("{\"cmd\":\"editor_continue\"}");
}

void
mcgdb_cmd_frame_up(void) {
  send_pkg_to_gdb ("{\"cmd\":\"editor_frame_up\"}");
}

void
mcgdb_cmd_frame_down(void) {
  send_pkg_to_gdb ("{\"cmd\":\"editor_frame_down\"}");
}

void
mcgdb_cmd_finish(void) {
  send_pkg_to_gdb ("{\"cmd\":\"editor_finish\"}");
}


void
mcgdb_cmd_print(void) {

}


void
__message_assert (const char *EX, const char *filename, int line) {
  char *str;
  asprintf (&str,"'%s' AT %s : %d",EX,filename,line);
  edit_error_dialog("ASSERT FAILED",str);
  abort();
}
