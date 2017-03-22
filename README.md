# mcgdb

Проект `mcgdb` представляет из себя объединение отладчика `gdb` и текстового редактора `mcedit`,
вкачестве front-end. Редактор `mcedit` служит для отображения текущей позиции исполнения и точек останова.  
  
  
![](https://github.com/dzabraev/mcgdb/blob/master/doc/img/mcgdb-title.png?raw=true "")
  
На рисунке изображено два окна. В правом окне запущен `gdb`. В левом окне открыт редактор mcedit.
Широкой красной линией отображена текущая строка текущего фрейма `gdb`. Красная отметка на номере
строки(столбец с номерами строк) иллюстрирует точку останова.

При помощи кликов по столбцам с номерами строк можно добавлять и удалять точки останова.

Для использования `mcgdb` необходим стандартный отладчик `gdb >= 7.12` и `mc` с нашими правками.

# INSTALL

## dependencies
1. `gdb >= 7.12` (compiled with `./configure --with-python` .Type in gdb-shell `(gdb) pi 1+1`, if error occur then your gdb compiled without python)
2. `mc`
3. `gnome-terminal`
4. `libjansson >= 2.9`

### install dependencies

```
  wget https://ftp.gnu.org/gnu/gdb/gdb-7.12.tar.xz  
  tar xvJf gdb-7.12.tar.xz  
  cd gdb-7.12  
  ./configure --with-python  
  make -j4  
  checkinstall  


  wget http://www.digip.org/jansson/releases/jansson-2.9.tar.gz  
  tar xzvf jansson-2.9.tar.gz  
  mv jansson-2.9 libjansson-2.9
  cd libjansson-2.9  
  ./configure  
  make -j4  
  checkinstall  
```

## INSTALL from sources

```
wget https://github.com/dzabraev/mcgdb/releases/download/1.1/mcgdb-1.1.tar.gz
tar xzvf mcgdb-1.1.tar.gz
mkdir obj-mcgdb-1.1  
cd obj-mcgdb-1.1  
../mcgdb-1.1/configure  
make -j4  
checkinstall (or make install)  
```

#getting started

Just use `$ mcgdb` instead `$ gdb`. When you invoke mcgdb additional windows will be
open automatically. 

OR you can load python plugin manually:  
```
$ gdb  
(gdb) source /usr/share/mcgdb/python/mcgdb_const.py  
(gdb) source /usr/share/mcgdb/python/mcgdb.py  
(gdb) mcgdb open main  
```

##gdb commands
mcgdb add several commands in gdb. Type
`(gdb) help mcgdb` to get command documentation.

Most important command is
`(gdb) mcgdb open main`. If you close window with editor,
then type this command and window will be reopen.

In this project mcedit is readonly. And onto ordinary keys we
add additional functionality.

1. `s == step`
1. `n == next`
1. `c == continue`
1. `u == up`
1. `d == down`
1. `b == break`

Focus editor and type `c`. This action produce
`(gdb) continue` command in gdb.

Key `b` get current cursor line in editor and filename of opened file
and produce `(gdb) break FILENAME:LINE`



