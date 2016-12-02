define hook-quit
  pi stop_event_loop()
end

define hookpost-up
  pi check_frame()
end


define hookpost-down
  pi check_frame()
end


define hookpost-frame
  pi check_frame()
end


