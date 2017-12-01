#ifndef _GNU_SOURCE
#   define _GNU_SOURCE 1
#endif

#include <config.h>


#include <stdio.h>

#include <sys/socket.h>
#include <netinet/in.h>
#include <sys/types.h>
#include <arpa/inet.h>
#include <stdlib.h>
#include <assert.h>


//#include "src/editor/edit.h"
#include "lib/global.h"
#include "lib/widget.h"

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
#include "src/mcgdb-bp-widget.h"
#include "lib/widget/mcgdb_aux_widget.h"
#include "lib/widget/mcgdb_asm_widget.h"


#define STREQ(s1,s2) (!strncmp(s1,s2,strlen(s2)))
gboolean disable_gdb_events=FALSE; /*turn off delivering gdb events to widgets*/
gboolean mcgdb_wait_gdb;
int mcgdb_listen_port;
int gdb_input_fd;

int selected_thread_global_num=-1;
GList *thread_list;

gboolean read_gdb_events;
gboolean mcgdb_exit_from_loop;

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

static gboolean
evt_convertable_to_key(struct gdb_action * gdb_evt);

static void
thread_entry_destroy (thread_entry_t *entry) {
  g_free (entry->name);
}

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
  message_assert (json_is_object(pkg));
  free(buf);
  return pkg;

}

enum gdb_cmd
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
    /*editor commands*/
    if(      compare_cmd("mark"))               {return MCGDB_MARK;}
    else if (compare_cmd("unmark_all"))         {return MCGDB_UNMARK_ALL;}
    else if (compare_cmd("unmark"))             {return MCGDB_UNMARK;}
    else if (compare_cmd("goto"))               {return MCGDB_GOTO;}
    else if (compare_cmd("fopen") )             {return MCGDB_FOPEN;}
    else if (compare_cmd("fclose") )            {return MCGDB_FCLOSE;}
    else if (compare_cmd("insert_str"))         {return MCGDB_INSERT_STR;}
    else if (compare_cmd("update_threads"))     {return MCGDB_UPDATE_THREADS;}
    else if (compare_cmd("bpsdel"))             {return MCGDB_BPSDEL;}
    else if (compare_cmd("bpsupd"))             {return MCGDB_BPSUPD;}

    else if (compare_cmd("set_window_type"))    {return MCGDB_SET_WINDOW_TYPE;}
    else if (compare_cmd("set_curline"))        {return MCGDB_SET_CURLINE;}
    else if (compare_cmd("exit"))               {return MCGDB_EXIT;}
    else if (compare_cmd("error_message"))      {return MCGDB_ERROR_MESSAGE;}
    else if (compare_cmd("update_nodes"))       {return MCGDB_UPDATE_NODES;}
    else if (compare_cmd("do_row_visible"))     {return MCGDB_DO_ROW_VISIBLE;}
    else if (compare_cmd("exemplar_create"))    {return MCGDB_EXEMPLAR_CREATE;}
    else if (compare_cmd("exemplar_drop"))      {return MCGDB_EXEMPLAR_DROP;}
    else if (compare_cmd("exemplar_set"))       {return MCGDB_EXEMPLAR_SET;}
    else if (compare_cmd("exemplar_copy"))      {return MCGDB_EXEMPLAR_COPY;}
    else if (compare_cmd("transaction"))        {return MCGDB_TRANSACTION;}
    else if (compare_cmd("drop_rows"))          {return MCGDB_DROP_ROWS;}
    else if (compare_cmd("drop_nodes"))         {return MCGDB_DROP_NODES;}
    else if (compare_cmd("insert_rows"))        {return MCGDB_INSERT_ROWS;}
    else if (compare_cmd("call_cb"))            {return MCGDB_CALL_CB;}
    else {
      cmd = MCGDB_UNKNOWN;
      message_assert (cmd!=MCGDB_UNKNOWN);
      return MCGDB_UNKNOWN;
    }
  }
  json_decref(val);
  return cmd;
}

static GHashTable * __data_hashtable__ = NULL;

int
data_ptr_register (void *data) {
  static int callback_id=1;
  callback_id++;
  if (!__data_hashtable__) {
    __data_hashtable__ = g_hash_table_new (g_direct_hash, g_direct_equal);
  }
  g_hash_table_insert (__data_hashtable__, GINT_TO_POINTER (callback_id), data);
  return callback_id;
}

static void *
data_ptr_lookup (int callback_id) {
  gpointer data;
  message_assert (__data_hashtable__ != NULL);
  data = g_hash_table_lookup (__data_hashtable__, GINT_TO_POINTER (callback_id));
  g_hash_table_remove (__data_hashtable__, GINT_TO_POINTER (callback_id));
  return data;
}

static void
check_action_from_gdb(struct gdb_action * act) {
  enum gdb_cmd cmd;
  json_t *pkg;
  pkg = read_pkg_from_gdb();
  message_assert (json_is_object(pkg));
  cmd=get_command_num(pkg);
  if (cmd==MCGDB_ERROR_MESSAGE) {
    edit_error_dialog("ERROR",json_string_value (json_object_get (pkg,"message")));
    act->command=MCGDB_NONE;
    act->pkg=NULL;
  }
  else if(cmd==MCGDB_CALL_CB) {
    void (*cb) (void *data);
    int type;
    cbPair *pair = data_ptr_lookup(myjson_int(pkg,"callback_id"));
    message_assert(pair!=NULL);
    type = myjson_int(pkg,"type");
    message_assert (type==CALLBACK_SUCCESS || type==CALLBACK_ERROR);
    cb = (type==CALLBACK_SUCCESS) ? pair->succ : pair->err;
    cb (pair->args);
    free (pair->args);
    free (pair);
    act->command=MCGDB_NONE;
    act->pkg=NULL;
  }
  else {
    act->command=cmd;
    act->pkg=pkg;
  }
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
  assert(act->command!=MCGDB_FCLOSE && act->command!=MCGDB_EXIT);
  switch(act->command) {
    case MCGDB_MARK:
      pkg_mark (pkg,edit);
      break;
    case MCGDB_UNMARK:
      pkg_unmark (pkg,edit);
      break;
    case MCGDB_UNMARK_ALL:
      pkg_unmark_all (edit);
      break;
    case MCGDB_UPDATE_THREADS:
      {
        json_t *info = json_object_get (pkg, "info");
        json_t *json_thread_list = json_object_get (info, "thread_list");

        g_list_free_full (thread_list, (GDestroyNotify)thread_entry_destroy);
        thread_list = NULL;

        selected_thread_global_num = myjson_int (info, "selected_thread");

        for (int idx=0,l = json_array_size (json_thread_list); idx<l; idx++) {
          json_t *th = json_array_get (json_thread_list, idx);
          thread_entry_t *entry = g_new0 (thread_entry_t, 1);
          entry->name           = g_strdup (myjson_str (th, "name"));
          entry->num            = myjson_int (th, "num");
          entry->global_num     = myjson_int (th, "global_num");
          entry->pid            = myjson_int (th, "pid");
          entry->lwp            = myjson_int (th, "lwp");
          entry->tid            = myjson_int (th, "tid");
          thread_list = g_list_append (thread_list, entry);
        }
      }
      break;
    case MCGDB_BPSDEL:
      pkg_bps_del (pkg);
      break;
    case MCGDB_BPSUPD:
      pkg_bps_upd (pkg);
      break;
    case MCGDB_GOTO:
      pkg_goto (pkg,edit);
      break;
    case MCGDB_SET_CURLINE:
      pkg_set_curline(pkg,edit);
      break;
    case MCGDB_INSERT_STR:
      edit_print_string (edit, json_string_value (json_object_get (pkg,"msg")));
      edit->modified=FALSE; /*prevent asking about saving*/
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
    asprintf (&pkg,"{\"cmd\":\"onclick\",\"onclick\":\"breakpoint\",\"line\": %ld}",click_line);
  }
  if (pkg)
    send_pkg_to_gdb (pkg);
    free (pkg);
  return;
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
    case MCGDB_EXIT:
      d_key=KEY_F(19);
      mcgdb_exit_from_loop = TRUE;
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
  read_gdb_events = !disable_gdb_events && ((find_editor (h)!=NULL) || is_mcgdb_aux_dialog (h) || is_mcgdb_asm_dialog (h));
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
mcgdb_module_init(void) {
  mcgdb_curline=-1;
  mcgdb_current_line_color   = tty_try_alloc_color_pair2 ("red", "black",   "bold", FALSE);
  mcgdb_bp_color_normal      = tty_try_alloc_color_pair2 ("red", "black",   NULL, FALSE);
  mcgdb_bp_color_disabled    = tty_try_alloc_color_pair2 ("red", "wite",    NULL, FALSE);
  mcgdb_bp_color_wait_update = tty_try_alloc_color_pair2 ("red", "yellow",  NULL, FALSE);
  mcgdb_bp_color_wait_remove = tty_try_alloc_color_pair2 ("red", "magenta", NULL, FALSE);
  mcgdb_bp_frame_color_wait_delete =
                               tty_try_alloc_color_pair2 ("yellow", "cyan", NULL, FALSE);
  option_line_state=1;
}


void
mcgdb_cmd_breakpoint (WEdit * edit) {
  mcgdb_bp_process_click (edit->filename, edit->buffer.curs_line+1, 1, 1);
}

void
mcgdb_cmd_disableenable_bp (WEdit * edit) {
  (void) edit;
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
mcgdb_shellcmd (const char *cmd) {
  /*execute `cmd` in gdb shell */
  char *json_cmd;
  asprintf(&json_cmd,"{\"cmd\":\"exec_in_gdb\", \"exec_in_gdb\":\"%s\"}",cmd);
  send_pkg_to_gdb (json_cmd);
  free (json_cmd);
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


gboolean
mcgdb_src_dlg(void) {
  mcgdb_exit_from_loop=FALSE;
  mcgdb_module_init();
  mcgdb_bp_module_init();
  while (!mcgdb_exit_from_loop) {
    vfs_path_t *vfs_filename;
    json_t * pkg = read_pkg_from_gdb();
    gdb_cmd_t cmd = get_command_num(pkg);
    const char *filename = json_string_value (json_object_get (pkg, "filename"));
    long line = json_integer_value (json_object_get (pkg, "line"));
    message_assert (cmd==MCGDB_FOPEN);
    vfs_filename = filename ? vfs_path_build_filename(filename, (char *) NULL) : NULL;
    edit_file (vfs_filename,line);
    vfs_path_free (vfs_filename);
  }
  mcgdb_bp_module_free();
  return TRUE;
}



