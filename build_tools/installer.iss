; ============================================================================
;  MiniMax Check-in — Inno Setup 安裝程式腳本
;
;  由 packaging\build.py 呼叫，例如：
;     ISCC.exe /DAppVersion=1.0.0 /DFlavor=full packaging\installer.iss
;
;  設計重點：
;   * 程式安裝到 {autopf}（Program Files；無管理員權限時為 LocalAppData\Programs）
;     —— **絕不將程式檔案放到桌面**。
;   * 桌面捷徑為「選用」且預設「不勾選」；使用者勾選才會在桌面建立 .lnk。
;   * 開始功能表捷徑一律建立；控制台「應用程式與功能」會出現卸載項目。
;   * 卸載時詢問是否一併刪除使用者資料（預設保留）。
; ============================================================================

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef Flavor
  #define Flavor "full"
#endif
#define ProjectRoot ".."
#define AppName "MiniMax Check-in"
#define AppNameCN "MiniMax 自動簽到"
#define Publisher "Minimax Check-in Project"
#define ExeName "MinimaxCheckin.exe"
#define BundleDir ProjectRoot + "\dist\MinimaxCheckin"

[Setup]
AppId={{8F3A6C51-2B7E-4D49-9C3A-5E1D7B9A4C21}
AppName={#AppNameCN}（{#AppName}）
AppVersion={#AppVersion}
AppVerName={#AppNameCN} {#AppVersion}
AppPublisher={#Publisher}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#Publisher}
VersionInfoDescription={#AppNameCN} 安裝程式
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppNameCN}
DisableProgramGroupPage=yes
AllowNoIcons=yes
UninstallDisplayName={#AppNameCN} {#AppVersion}
UninstallDisplayIcon={app}\{#ExeName}
OutputDir={#ProjectRoot}\dist\installer
OutputBaseFilename=MiniMaxCheckin-Setup-{#AppVersion}-{#Flavor}
SetupIconFile={#ProjectRoot}\assets\app.ico
LicenseFile={#ProjectRoot}\LICENSE
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
AppMutex=MinimaxCheckin.SingleInstance
CloseApplications=yes
RestartApplications=no
AllowUNCPath=no
; 讓使用者可在精靈中選擇安裝範圍（僅我 / 所有人）
DisableWelcomePage=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑（選用）"; GroupDescription: "其他選項："; Flags: unchecked
Name: "startup"; Description: "開機時自動在背景啟動（可稍後於程式設定中變更）"; GroupDescription: "其他選項："; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 若目錄已有舊版檔案，全部覆蓋（版本升級）

[Icons]
Name: "{group}\{#AppNameCN}"; Filename: "{app}\{#ExeName}"; Comment: "MiniMax Agent 每日自動簽到"
Name: "{group}\{cm:UninstallProgram,{#AppNameCN}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppNameCN}"; Filename: "{app}\{#ExeName}"; Comment: "MiniMax Agent 每日自動簽到"; Tasks: desktopicon

[Registry]
; 讓應用程式的「開機自啓動」設定在安裝與卸載時保持乾淨
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "MinimaxCheckin"; \
    ValueData: """{app}\{#ExeName}"" --minimized"; \
    Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#ExeName}"; Description: "啟動 {#AppNameCN}"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
; 卸載前先結束仍在執行的程式（Mutex 由 Inno 的 CloseApplications 處理，這裡再做保險）
Filename: "{cmd}"; Parameters: "/C taskkill /IM {#ExeName} /F >nul 2>&1"; \
    Flags: runhidden; RunOnceId: "KillApp"

[Code]
{ 卸載後：清除開機自啓動機碼，並詢問是否刪除使用者資料 }
procedure TryDeleteRunValue();
begin
  { 值可能不存在（使用者未開啟自啓動），必須包在 try 中避免中斷卸載 }
  try
    RegDeleteValue(HKEY_CURRENT_USER,
      'Software\Microsoft\Windows\CurrentVersion\Run', 'MinimaxCheckin');
  except
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Response: Integer;
  RoamingDir: String;
  LocalDir: String;
begin
  if CurUninstallStep <> usPostUninstall then
    exit;

  TryDeleteRunValue();

  { 靜默卸載時不詢問，預設保留使用者資料 }
  if UninstallSilent() then
    exit;

  RoamingDir := ExpandConstant('{userappdata}\MinimaxCheckin');
  LocalDir := ExpandConstant('{localappdata}\MinimaxCheckin');

  if (not DirExists(RoamingDir)) and (not DirExists(LocalDir)) then
    exit;

  Response := MsgBox('是否一併刪除您的設定與帳號登入資料？' + #13#10 + #13#10 +
                     '選擇「否」會保留資料，日後重新安裝可沿用既有設定與登入狀態。' + #13#10 + #13#10 +
                     '設定檔：' + RoamingDir + #13#10 +
                     '本機資料：' + LocalDir,
                     mbConfirmation, MB_YESNO or MB_DEFBUTTON2);
  if Response = IDYES then
  begin
    DelTree(RoamingDir, True, True, True);
    DelTree(LocalDir, True, True, True);
  end;
end;