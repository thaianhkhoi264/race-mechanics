# Running unattended on Windows

`scripts/racemech-hidden.vbs <command>` runs `racemech <command>` from the repo root with no
console window and appends its output to `data/<command>.log`.

`scripts/racemech-logon.vbs` runs `sync`, waits for it to finish, then starts `serve`, so the
server never loads stale data. If sync fails (offline, a source unreachable), `serve` still starts
with the data from the last good sync.

- **At logon:** put a shortcut in the Startup folder (`shell:startup`) to
  `wscript.exe "<repo>\scripts\racemech-logon.vbs"`, where `<repo>` is your checkout.
  Logon-triggered scheduled tasks need admin rights; the Startup folder doesn't.
- **Restart by hand:** stop the running `serve` process, then run
  `wscript.exe "<repo>\scripts\racemech-hidden.vbs" serve` (or a Task Scheduler entry that runs the
  same command on demand). `serve` reads the data only when it starts, so restart it after a
  manual `racemech sync`.
