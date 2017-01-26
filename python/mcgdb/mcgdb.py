from abc import ABCMeta, abstractmethod, abstractproperty
import sys,os,select,errno
import json

import gdb

class Entity(object):
  def gdb_print(self,msg):
    raise NotImplementedError


class BaseWindow(Entity):

  def __init__(self):
    lsock=socket.socket()
    lsock.bind( ('',0) )
    lsock.listen(1)
    lport=lsock.getsockname()[1]
    os.system('gnome-terminal -e "{path_to_mc} -e --gdb-port={gdb_port}"'.format(
      path_to_mc=PATH_TO_MC,gdb_port=lport))
    conn = lsock.accept()[0]
    lsock.close()
    self.fd=conn.fileno()
    self.conn=conn
    self.send({
      'cmd' :'set_window_type',
      'type':self.type,
    })

  @abstractproperty
  def type(self):
    pass

  def send(self,msg):
    jmsg=json.dumps(msg)
    smsg='{len};{data}'.format(len(jmsg),jmsg)
    self.conn.sendall(smsg)
  def recv(self):
    lstr=''
    b=self.conn.recv(1)
    while b!=';'
      lstr+=b
      b=self.conn.recv(1)
    assert len(lstr)>0
    total=int(lstr)
    nrecv=0
    data=''
    while nrecv<total:
      try:
        data1=self.conn.recv(total-nrecv)
      except socket.error as se:
        if se[0]==errno.EINTR:
          continue
        else:
          raise
      if len(data1)==0:
        raise CommandReadFailure
      nrecv+=len(data1)
      data+=data1
    return json.loads(data)


class MainWindow(BaseWindow):

  type='main_window'
  startcmd='mcgdb mainwondow'

  def __init__(self,coregdb):
    coregdb.register(self)
    self.editor_cbs = [
      'editor_breakpoint'       :   __editor_breakpoint,
      'editor_breakpoint_de'    :   __editor_breakpoint_de,
      'editor_next'             :   __editor_next,
      'editor_step'             :   __editor_step,
      'editor_until'            :   __editor_until,
      'editor_continue'         :   __editor_continue,
    ]


  def byemsg(self):
    self.gdb_print("type `{cmd}` to restart {type}\n".format(cmd=self.startcmd,type=self.type))

  def gdb_inferior_stop(self):
    pass
  def gdb_inferior_exited(self):
    pass
  def gdb_new_objfile(self):
    pass
  def gdb_check_frame(self):
    pass
  def gdb_change_breakpoints(self):
    pass

  #commands from editor
  def __editor_breakpoint(self,pkg):
    line=pkg['line']
  def __editor_breakpoint_de(self,pkg):
    ''' Disable/enable breakpoint'''
    pass
  def __editor_next(self,pkg):
    pass
  def __editor_step(self,pkg):
    pass
  def __editor_until(self,pkg):
    pass
  def __editor_continue(self,pkg):
    pass


  def process_msg(self):
    '''Обработать сообщение из редактора'''
    pkg=self.recv()
    cmd=pkg['cmd']
    return self.editor_cbs[cmd](pkg)



class CoreGdb(object):
  def __init__(self,rfd):
    self.fd=rfd
    self.entities=[]
  def process_msg(self):
    '''Обработать сообщение от gdb'''
    pass
  def register(self,entity):
    if entity not in self.entities:
      self.entities.append(entity)
  def unregister(self,entity):
    self.entities.remove(entity)


def event_loop(gdb_rfd):
  coregdb=Gdb(gdb_rfd)
  entities=[]
  entities.append( coregdb )
  entities.append( MainWindow(coregdb) )
  fte={}
  for ent in entities:
    fte[ent.fd]=ent
  while True:
    rfds=fte.keys()
    if len(rfds)==0:
      #nothing to be doing
      gdb_print('nothing tobe doing\n')
      break
    timeout=0.1
    #timeout ставится чтобы проверять, нужно ли останавливать этот цикл
    try:
      fds=select.select(rfds,[],[],timeout)
    except select.error as se:
      if se[0]==errno.EINTR:
        continue
      else:
        raise
    ready_rfds=fds[0]
    for fd in ready_rfds:
      entity=fte[fd]
      try:
        entity.process_msg()
      except CommandReadFailure:
        #возможно удаленное окно было закрыто =>
        #уничтожаем объект, который соответствует
        #потерянному окну.
        assert fd!=coregdb.fd
        coregdb.unregister(entity)
        del fte[fd]
        gdb_print('connection type={} was closed\n'.format(entity.type))
        entity.byemsg()
  gdb_print('event_loop stopped\n')

