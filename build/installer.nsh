!macro preInit
  ; Terminate any lingering claudexit installer PROCESS to release the mutex.
  ; WM_CLOSE is unreliable on MB_RETRYCANCEL dialogs (close button disabled),
  ; so we use GetWindowThreadProcessId + TerminateProcess instead.
  StrCpy $0 ""
  findSetupLoop:
    FindWindow $0 "#32770" "" "" $0
    StrCmp 0 $0 findSetupDone
    System::Call 'user32::GetWindowText(p r0, t .r1, i 256)'
    StrCmp $1 "claudexit Setup" 0 findSetupLoop
    System::Call 'user32::GetWindowThreadProcessId(p r0, *i .r2)'
    System::Call 'kernel32::OpenProcess(i 1, i 0, i r2) p.r3'
    StrCmp $3 0 findSetupLoop
    System::Call 'kernel32::TerminateProcess(p r3, i 1)'
    System::Call 'kernel32::CloseHandle(p r3)'
    Sleep 1500
    StrCpy $0 ""
    Goto findSetupLoop
  findSetupDone:
!macroend

!macro customInit
  ; Kill claudexit + backend at installer start (.onInit, Stage 1)
  nsExec::Exec 'taskkill /F /IM claudexit.exe'
  Pop $0
  nsExec::Exec 'taskkill /F /IM claudexit-backend.exe'
  Pop $0
  Sleep 2000
!macroend

!macro customCheckAppRunning
  ; Replace default _CHECK_APP_RUNNING — silent kill, no dialogs possible
  ; Called in both installer (before uninstall) and uninstaller (.onInit)
  nsExec::Exec 'taskkill /F /IM claudexit.exe'
  Pop $0
  nsExec::Exec 'taskkill /F /IM claudexit-backend.exe'
  Pop $0
  Sleep 2000
!macroend

!macro customRemoveFiles
  ; Replace un.atomicRMDir which Aborts (returning non-zero) if any file is locked.
  ; RMDir /r silently skips locked files instead of aborting — uninstaller always succeeds.
  nsExec::Exec 'taskkill /F /IM claudexit.exe'
  Pop $0
  nsExec::Exec 'taskkill /F /IM claudexit-backend.exe'
  Pop $0
  Sleep 3000
  RMDir /r "$INSTDIR"
!macroend

!macro customUnInstallCheck
  IfErrors 0 +2
    DetailPrint "Old uninstaller not found — continuing with fresh install."
  ${if} $R0 != 0
    DetailPrint "Old uninstaller exited with code $R0 — continuing anyway."
  ${endif}
!macroend
