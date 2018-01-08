# mcgdb

Tui fornt-end for debugger `gdb` based on midnight commander.
  
  
![](https://github.com/dzabraev/mcgdb/blob/master/doc/img/mcgdb-title.png?raw=true "")
  
Two windows is shown in this picture. Upper left window has started `gdb` and right window has started src window.
Black mark with red text in line 543 illustrates breakpoint. The current execution position is marked with color
like breakpoint.

You can add and delete breakpoints by produce clicks on columns with line numbers.

# INSTALL

1. install nix package manager https://nixos.org/nix/
2. wget https://github.com/dzabraev/mcgdb/releases/download/v1.4-beta/mcgdb.nix
3. `nix-env -f mcgdb.nix -iA mcgdb`
4. run `$ mcgdb a.out` in your shell

# getting started

Just use `$ mcgdb` instead `$ gdb`. When you invoke mcgdb additional windows will be
opened automatically. 

## gdb commands
mcgdb add several commands in gdb. Type
`(gdb) help mcgdb` to get command documentation.

```
(gdb) mcgdb open aux
(gdb) mcgdb open src
(gdb) mcgdb open asm
```

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

Key `b` gets current cursor line in editor and filename of opened file
and produce `(gdb) break FILENAME:LINE`



