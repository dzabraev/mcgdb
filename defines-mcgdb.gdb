define hook-quit
python
stop_event_loop()
end
end

define hookpost-up
python
check_frame()
end
end


define hookpost-down
python
check_frame()
end
end


define hookpost-frame
python
check_frame()
end
end


