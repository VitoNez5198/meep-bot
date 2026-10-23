' Inicia Meep Bot en segundo plano (minimizado en la bandeja del sistema junto al reloj).
' No abre ninguna ventana de consola negra.
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
ScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = ScriptDir

On Error Resume Next
WshShell.Run "pythonw.exe main.py", 0, False
If Err.Number <> 0 Then
    WshShell.Run "python.exe main.py", 1, False
    If Err.Number <> 0 Then
        MsgBox "No se encontro Python instalado en el sistema." & vbCrLf & "Por favor asegurate de instalar Python y marcar 'Add python.exe to PATH'.", vbCritical, "Meep Bot"
    End If
End If
