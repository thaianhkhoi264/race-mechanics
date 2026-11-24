' Logon entry point: runs `racemech sync`, waits for it to finish, then starts `racemech serve`,
' so serve never loads yesterday's data. Serve starts even if sync fails (offline, remote host down):
' it then serves the data from the last good sync. Both run hidden via racemech-hidden.vbs and
' log to data\sync.log / data\serve.log. Point one Startup-folder shortcut at this script:
'     wscript.exe "<repo>\scripts\racemech-logon.vbs"
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
hidden = """" & fso.GetParentFolderName(WScript.ScriptFullName) & "\racemech-hidden.vbs"""
sh.Run "wscript.exe " & hidden & " sync", 0, True
sh.Run "wscript.exe " & hidden & " serve", 0, False
