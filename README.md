# mcgdb

Проект mcgdb представляет из себя объединение отладчика gdb и текстового редактора mcedit,
вкачестве front-end. Редактор mcedit служит для отображения текущей позиции исполнения и точек останова.  
  
  
![](https://github.com/dzabraev/mcgdb/blob/master/doc/img/mcgdb-title.png?raw=true "")
  
На рисунке изображено два окна. В правом окне запущен gdb. В левом окне открыт редактор mcedit.
Широкой красной линией отображена текущая строка текущего фрейма gdb. Красная отметка на номере
строки(столбец с номерами строк) иллюстрирует точку останова.

При помощи кликов по столбцам с номерами строк можно добавлять и удалять точки останова.

Для использования mcgdb необходим стандартный отладчик gdb >= 7.12 и mc с нашими правками.

# INSTALL

## dependencies
1. gdb >= 7.12 (compiled with ./configure --with-python .Type in gdb-shell pi 1+1, if error occur then your gdb compiled without python)
2. mc
3. gnome-terminal
4. libjansson >= 2.9

### install dependencies


  wget https://ftp.gnu.org/gnu/gdb/gdb-7.12.tar.xz  
  tar xvJf gdb-7.12.tar.xz  
  cd gdb-7.12  
  ./configure  
  make -j4  
  checkinstall  


  wget http://www.digip.org/jansson/releases/jansson-2.9.tar.gz  
  tar xzvf jansson-2.9.tar.gz  
  mv jansson-2.9 libjansson-2.9
  cd libjansson-2.9  
  ./configure  
  make -j4  
  checkinstall  


## INSTALL from sources

git clone https://github.com/dzabraev/mcgdb  
mkdir obj-mcgdb  
cd obj-mcgdb  
../mcgdb/configure  
make -j4  
checkinstall  

#getting started
Just use `$ mcgdb` instead `$ gdb`. When you invoke mcgdb additional windows will be
open automatically. 

OR you can load python plugin manually:  
$ gdb  
(gdb) source /usr/share/mcgdb/python/mcgdb_const.py  
(gdb) source /usr/share/mcgdb/python/mcgdb.py  
(gdb) mcgdb open main  




