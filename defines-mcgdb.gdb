define hook-quit
python
mcgdb_main.notify_shellcmd('quit')
end
end

define hook-disable
python
mcgdb_main.notify_shellcmd('bp_disable')
end
end

define hook-enable
python
mcgdb_main.notify_shellcmd('bp_enable')
end
end


define hookpost-up
python
mcgdb_main.notify_shellcmd('frame_up')
end
end


define hookpost-down
python
mcgdb_main.notify_shellcmd('frame_down')
end
end


define hookpost-frame
python
mcgdb_main.notify_shellcmd('frame')
end
end


define hookpost-thread
python
mcgdb_main.notify_shellcmd('thread')
end
end


