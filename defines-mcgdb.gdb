define hook-quit
python
from mcgdb.common import McgdbMain
McgdbMain().notify_shellcmd('quit')
end
end

define hook-disable
python
from mcgdb.common import McgdbMain
McgdbMain().notify_shellcmd('disable')
end
end

define hook-enable
python
from mcgdb.common import McgdbMain
McgdbMain().notify_shellcmd('enable')
end
end


define hookpost-up
python
from mcgdb.common import McgdbMain
McgdbMain().notify_shellcmd('up')
end
end


define hookpost-down
python
from mcgdb.common import McgdbMain
McgdbMain().notify_shellcmd('down')
end
end


define hookpost-frame
python
from mcgdb.common import McgdbMain
McgdbMain().notify_shellcmd('frame')
end
end


define hookpost-thread
python
from mcgdb.common import McgdbMain
McgdbMain().notify_shellcmd('thread')
end
end

set history save on
