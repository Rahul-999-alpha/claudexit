!macro customInit
  ; Kill existing claudexit processes before install/update
  nsExec::ExecToStack 'tasklist /FI "IMAGENAME eq claudexit.exe" /NH'
  Pop $0
  Pop $1
  StrCmp $1 "" done
  ${If} $1 != "INFO: No tasks are running which match the specified criteria."
    ; Gracefully close the Electron app
    nsExec::ExecToStack 'taskkill /IM claudexit.exe'
    Sleep 3000
    ; Force-kill the backend subprocess
    nsExec::ExecToStack 'taskkill /F /IM claudexit-backend.exe'
    Sleep 2000
    ; Force-kill main app if still hanging
    nsExec::ExecToStack 'taskkill /F /IM claudexit.exe'
    Sleep 1000
  ${EndIf}
  done:
!macroend
