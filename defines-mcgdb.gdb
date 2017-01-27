define hook-quit
python
mcgdb_main.stop_event_loop()
end
end

define hookpost-up
python
mcgdb_main.notify_check_frame()
end
end


define hookpost-down
python
mcgdb_main.notify_check_frame()
end
end


define hookpost-frame
python
mcgdb_main.notify_check_frame()
end
end


