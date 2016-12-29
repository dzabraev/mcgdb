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

## dependancies
1. gdb >= 7.12
2. mc

## INSTALL from sources

git clone https://github.com/dzabraev/mcgdb
mkdir obj-mcgdb
cd obj-mcgdb
../mcgdb/configure
make -j4
make install
