' Runs `racemech <args>` from the repo root without a console window, appending its output to
' data\<first arg>.log. Used by the Windows Task Scheduler entries (see README "Serving
' bot_repo"), e.g.:   wscript.exe scripts\racemech-hidden.vbs serve
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
If WScript.Arguments.Count = 0 Then WScript.Quit 2
args = ""
For Each a In WScript.Arguments
    args = args & " " & a
Next
If Not fso.FolderExists(root & "\data") Then fso.CreateFolder(root & "\data")
sh.CurrentDirectory = root
cmd = "cmd /c set PYTHONIOENCODING=utf-8&& """ & root & "\.venv\Scripts\racemech.exe""" & args & _
      " >> """ & root & "\data\" & WScript.Arguments(0) & ".log"" 2>&1"
WScript.Quit sh.Run(cmd, 0, True)
