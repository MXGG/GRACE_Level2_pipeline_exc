#define MyAppName "GRACE-L2"
#define MyAppVersion "V01"
#define MyAppNumericVersion "1.0.0.0"
#define MyAppDescription "GRACE 二级数据处理流程，包括滤波、流域分析、预览"
#define MyAppDeveloper "LLX"
#define MyAppOrganizationCN "华中科技大学 国家精密重力测量科学中心 地球物理组"
#define MyAppOrganizationEN "HUST, National Gravity Laboratory, Institute of Geophysics"
#define MyAppPublisher "LLX - HUST National Gravity Laboratory"
#define MyAppCopyright "Copyright (C) 2026 LLX, HUST National Gravity Laboratory, Institute of Geophysics. All rights reserved."
#define MyAppExeName "grace-pipeline-gui.exe"
#define MyAppDefaultDir "D:\Program Files (x86)\GRACE_L2"

[Setup]
AppId={{8D8E3C69-4E35-4B62-9C83-6E7219E6D2E5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments={#MyAppDescription}
AppCopyright={#MyAppCopyright}
DefaultDirName={code:GetDefaultDir}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
DisableDirPage=no
DisableProgramGroupPage=no
UsePreviousAppDir=no
CreateAppDir=yes

OutputDir=..\release
OutputBaseFilename=GRACE-L2-Setup-V01
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes

; 默认安装到 D:\Program Files (x86)\GRACE_L2，建议使用管理员权限以避免目录权限问题。
; 如不希望弹出 UAC，可改为 PrivilegesRequired=lowest，但安装到类 Program Files 目录时可能失败。
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\dist\{#MyAppExeName}
SetupIconFile=grace-l2.ico
ChangesEnvironment=yes
CloseApplications=yes
RestartApplications=no

VersionInfoVersion={#MyAppNumericVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppDescription}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppNumericVersion}
VersionInfoProductTextVersion={#MyAppVersion}
VersionInfoTextVersion={#MyAppVersion}
VersionInfoCopyright={#MyAppCopyright}

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项："; Flags: unchecked
Name: "datalinks"; Description: "创建数据目录和输出目录快捷方式"; Flags: checkedonce
Name: "setenv"; Description: "写入 GRACE_L2_HOME、GRACE_L2_DATA、GRACE_L2_OUTPUT 环境变量"; Flags: checkedonce

[Files]
; 主程序
Source: "..\dist\*"; DestDir: "{app}\dist"; Flags: ignoreversion recursesubdirs createallsubdirs

; 程序数据：统一安装到 {app}\data，避免落入 C:\Users\...\AppData
Source: "..\data\Boundary\*"; DestDir: "{app}\data\Boundary"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\data\DDK\*"; DestDir: "{app}\data\DDK"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\data\GRACE\GIA\*"; DestDir: "{app}\data\GRACE\GIA"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\data\GRACE\LowDegree\*"; DestDir: "{app}\data\GRACE\LowDegree"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; data/output 目录允许普通用户写入，避免安装到 Program Files 类目录后程序无法生成结果。
Name: "{app}\data"; Permissions: users-modify
Name: "{app}\data\GRACE"; Permissions: users-modify
Name: "{app}\data\GRACE\GSM"; Permissions: users-modify
Name: "{app}\data\Hydro"; Permissions: users-modify
Name: "{app}\data\Hydro\GLDAS"; Permissions: users-modify
Name: "{app}\data\Hydro\TRMM"; Permissions: users-modify
Name: "{app}\data\Reference"; Permissions: users-modify
Name: "{app}\data\Reference\Mascon"; Permissions: users-modify
Name: "{app}\data\Validation"; Permissions: users-modify
Name: "{app}\data\Validation\TWSC_monthly"; Permissions: users-modify
Name: "{app}\output"; Permissions: users-modify
Name: "{app}\output\local"; Permissions: users-modify
Name: "{app}\output\remote"; Permissions: users-modify

[INI]
; 供程序读取的安装路径配置。建议程序优先读取此文件或环境变量，而不是写死 AppData。
Filename: "{app}\grace-l2.ini"; Section: "Paths"; Key: "HomeDir"; String: "{app}"
Filename: "{app}\grace-l2.ini"; Section: "Paths"; Key: "DataDir"; String: "{app}\data"
Filename: "{app}\grace-l2.ini"; Section: "Paths"; Key: "OutputDir"; String: "{app}\output"
Filename: "{app}\grace-l2.ini"; Section: "Paths"; Key: "DistDir"; String: "{app}\dist"

; 软件说明与版本信息。
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "Name"; String: "{#MyAppName}"
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "Version"; String: "{#MyAppVersion}"
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "Description"; String: "{#MyAppDescription}"
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "Developer"; String: "{#MyAppDeveloper}"
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "OrganizationCN"; String: "{#MyAppOrganizationCN}"
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "OrganizationEN"; String: "{#MyAppOrganizationEN}"
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "Copyright"; String: "{#MyAppCopyright}"

[Registry]
; 当前用户环境变量，便于程序或脚本定位安装目录。卸载时同步删除。
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "GRACE_L2_HOME"; ValueData: "{app}"; Flags: uninsdeletevalue; Tasks: setenv
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "GRACE_L2_DATA"; ValueData: "{app}\data"; Flags: uninsdeletevalue; Tasks: setenv
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "GRACE_L2_OUTPUT"; ValueData: "{app}\output"; Flags: uninsdeletevalue; Tasks: setenv

; 软件自身注册表配置。程序也可读取这里作为路径来源。
Root: HKCU; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "DataDir"; ValueData: "{app}\data"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "OutputDir"; ValueData: "{app}\output"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "Description"; ValueData: "{#MyAppDescription}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "Developer"; ValueData: "{#MyAppDeveloper}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "OrganizationCN"; ValueData: "{#MyAppOrganizationCN}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "OrganizationEN"; ValueData: "{#MyAppOrganizationEN}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "Copyright"; ValueData: "{#MyAppCopyright}"; Flags: uninsdeletekey

[Icons]
Name: "{group}\GRACE-L2"; Filename: "{app}\dist\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\数据目录"; Filename: "{app}\data"; Tasks: datalinks
Name: "{group}\输出目录"; Filename: "{app}\output"; Tasks: datalinks
Name: "{group}\配置文件"; Filename: "{app}\grace-l2.ini"; Tasks: datalinks
Name: "{group}\卸载 GRACE-L2"; Filename: "{uninstallexe}"

Name: "{autodesktop}\GRACE-L2"; Filename: "{app}\dist\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{autodesktop}\GRACE-L2 数据目录"; Filename: "{app}\data"; Tasks: desktopicon
Name: "{autodesktop}\GRACE-L2 输出目录"; Filename: "{app}\output"; Tasks: desktopicon

[Run]
Filename: "{app}\dist\{#MyAppExeName}"; Description: "启动 GRACE-L2"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"

[UninstallDelete]
; 只删除安装器生成的配置文件和空目录，不主动删除用户后续产生的数据成果。
Type: files; Name: "{app}\grace-l2.ini"
Type: dirifempty; Name: "{app}\output\local"
Type: dirifempty; Name: "{app}\output\remote"
Type: dirifempty; Name: "{app}\output"
Type: dirifempty; Name: "{app}\data\GRACE\GSM"
Type: dirifempty; Name: "{app}\data\Hydro\GLDAS"
Type: dirifempty; Name: "{app}\data\Hydro\TRMM"
Type: dirifempty; Name: "{app}\data\Hydro"
Type: dirifempty; Name: "{app}\data\Reference\Mascon"
Type: dirifempty; Name: "{app}\data\Reference"
Type: dirifempty; Name: "{app}\data\Validation\TWSC_monthly"
Type: dirifempty; Name: "{app}\data\Validation"
Type: dirifempty; Name: "{app}\data\GRACE"
Type: dirifempty; Name: "{app}\data"
Type: dirifempty; Name: "{app}"

[Code]
function GetDefaultDir(Param: string): string;
begin
  if DirExists('D:\') then
    Result := '{#MyAppDefaultDir}'
  else
    Result := ExpandConstant('{autopf32}\GRACE_L2');
end;
