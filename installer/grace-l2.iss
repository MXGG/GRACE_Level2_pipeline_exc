#define MyAppName "GRACE-L2"
#define MyAppVersion "0.1.0.0"
#define MyAppNumericVersion "0.1.0.0"
#define MyAppDescription "GRACE 二级数据处理流程，包括滤波、流域分析、预览"
#define MyAppDeveloper "LLX"
#define MyAppOrganizationCN "华中科技大学 国家精密重力测量科学中心 地球物理组"
#define MyAppOrganizationEN "HUST, National Gravity Laboratory, Institute of Geophysics"
#define MyAppPublisher "LLX - HUST National Gravity Laboratory"
#define MyAppCopyright "Copyright (C) 2026 LLX, HUST National Gravity Laboratory, Institute of Geophysics. All rights reserved."
#define MyAppExeName "grace-pipeline-gui.exe"
#define MyAppDefaultDir "D:\Program Files\GRACE_L2"

[Setup]
AppId={{8D8E3C69-4E35-4B62-9C83-6E7219E6D2E5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/MXGG/GRACE_Level2_pipeline_exc
AppSupportURL=https://github.com/MXGG/GRACE_Level2_pipeline_exc/issues
AppUpdatesURL=https://github.com/MXGG/GRACE_Level2_pipeline_exc/releases
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
OutputBaseFilename=grace-l2-pipeline-v{#MyAppVersion}-win-x64-setup

Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes

; winget machine scope requires an installer that can run silently with admin rights.
PrivilegesRequired=admin

; Inno Setup newer versions recommend x64compatible instead of deprecated x64.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Keep ARP display name clean. Version is recorded separately through AppVersion.
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\dist\{#MyAppExeName}

SetupIconFile=grace-l2.ico
ChangesEnvironment=yes
CloseApplications=yes
RestartApplications=no
MinVersion=10.0

VersionInfoVersion={#MyAppNumericVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppDescription}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppNumericVersion}
VersionInfoProductTextVersion={#MyAppVersion}
VersionInfoTextVersion={#MyAppVersion}
VersionInfoCopyright={#MyAppCopyright}

[Languages]
Name: "default"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项："; Flags: unchecked
Name: "datalinks"; Description: "创建数据目录、配置目录和输出目录快捷方式"; Flags: checkedonce
Name: "setenv"; Description: "写入 GRACE_L2_HOME、GRACE_L2_DATA、GRACE_L2_CONFIG、GRACE_L2_OUTPUT 环境变量"; Flags: checkedonce

[Files]
; 主程序
Source: "..\dist\*"; DestDir: "{app}\dist"; Flags: ignoreversion recursesubdirs createallsubdirs

; 共用配置
Source: "..\configs\*"; DestDir: "{app}\configs"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; 项目说明文件
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\README.zh-CN.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "grace-l2.ico"; DestDir: "{app}\resources"; Flags: ignoreversion

; 小型必要辅助数据。大型 GRACE/GSM、GLDAS、Mascon 等数据不建议打入安装包。
Source: "..\data\Boundary\*"; DestDir: "{app}\data\Boundary"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\data\DDK\*"; DestDir: "{app}\data\DDK"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\data\GRACE\GIA\*"; DestDir: "{app}\data\GRACE\GIA"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\data\GRACE\LowDegree\*"; DestDir: "{app}\data\GRACE\LowDegree"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

[Dirs]
; 配置目录允许用户修改 user.json。
Name: "{app}\configs"; Permissions: users-modify

; 数据目录。大型数据建议由用户后续放入对应目录。
Name: "{app}\data"; Permissions: users-modify
Name: "{app}\data\GRACE"; Permissions: users-modify
Name: "{app}\data\GRACE\GSM"; Permissions: users-modify
Name: "{app}\data\GRACE\GIA"; Permissions: users-modify
Name: "{app}\data\GRACE\LowDegree"; Permissions: users-modify
Name: "{app}\data\Hydro"; Permissions: users-modify
Name: "{app}\data\Hydro\GLDAS"; Permissions: users-modify
Name: "{app}\data\Hydro\TRMM"; Permissions: users-modify
Name: "{app}\data\Reference"; Permissions: users-modify
Name: "{app}\data\Reference\Mascon"; Permissions: users-modify
Name: "{app}\data\Validation"; Permissions: users-modify
Name: "{app}\data\Validation\TWSC_monthly"; Permissions: users-modify

; 规范输出目录
Name: "{app}\outputs"; Permissions: users-modify
Name: "{app}\outputs\local"; Permissions: users-modify
Name: "{app}\outputs\remote"; Permissions: users-modify
Name: "{app}\outputs\figures"; Permissions: users-modify
Name: "{app}\outputs\logs"; Permissions: users-modify

; 兼容旧版本 output 路径，避免旧代码写死 output 时失败。
Name: "{app}\output"; Permissions: users-modify
Name: "{app}\output\local"; Permissions: users-modify
Name: "{app}\output\remote"; Permissions: users-modify

[INI]
; 供程序读取的安装路径配置。程序应优先读取此文件或环境变量。
Filename: "{app}\grace-l2.ini"; Section: "Paths"; Key: "HomeDir"; String: "{app}"
Filename: "{app}\grace-l2.ini"; Section: "Paths"; Key: "DistDir"; String: "{app}\dist"
Filename: "{app}\grace-l2.ini"; Section: "Paths"; Key: "ConfigDir"; String: "{app}\configs"
Filename: "{app}\grace-l2.ini"; Section: "Paths"; Key: "DataDir"; String: "{app}\data"
Filename: "{app}\grace-l2.ini"; Section: "Paths"; Key: "OutputDir"; String: "{app}\outputs"
Filename: "{app}\grace-l2.ini"; Section: "Paths"; Key: "LegacyOutputDir"; String: "{app}\output"

; 软件说明与版本信息。
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "Name"; String: "{#MyAppName}"
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "Version"; String: "{#MyAppVersion}"
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "Description"; String: "{#MyAppDescription}"
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "Developer"; String: "{#MyAppDeveloper}"
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "Publisher"; String: "{#MyAppPublisher}"
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "OrganizationCN"; String: "{#MyAppOrganizationCN}"
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "OrganizationEN"; String: "{#MyAppOrganizationEN}"
Filename: "{app}\grace-l2.ini"; Section: "Application"; Key: "Copyright"; String: "{#MyAppCopyright}"

[Registry]
; Machine-scope environment variables. This is more consistent with winget machine-scope installation.
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: string; ValueName: "GRACE_L2_HOME"; ValueData: "{app}"; Flags: uninsdeletevalue; Tasks: setenv
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: string; ValueName: "GRACE_L2_DATA"; ValueData: "{app}\data"; Flags: uninsdeletevalue; Tasks: setenv
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: string; ValueName: "GRACE_L2_CONFIG"; ValueData: "{app}\configs"; Flags: uninsdeletevalue; Tasks: setenv
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: string; ValueName: "GRACE_L2_OUTPUT"; ValueData: "{app}\outputs"; Flags: uninsdeletevalue; Tasks: setenv

; 软件自身注册表配置。
Root: HKLM; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "DistDir"; ValueData: "{app}\dist"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "ConfigDir"; ValueData: "{app}\configs"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "DataDir"; ValueData: "{app}\data"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "OutputDir"; ValueData: "{app}\outputs"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "LegacyOutputDir"; ValueData: "{app}\output"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "Description"; ValueData: "{#MyAppDescription}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "Developer"; ValueData: "{#MyAppDeveloper}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "Publisher"; ValueData: "{#MyAppPublisher}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "OrganizationCN"; ValueData: "{#MyAppOrganizationCN}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "OrganizationEN"; ValueData: "{#MyAppOrganizationEN}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\GRACE-L2"; ValueType: string; ValueName: "Copyright"; ValueData: "{#MyAppCopyright}"; Flags: uninsdeletekey

[Icons]
Name: "{group}\GRACE-L2"; Filename: "{app}\dist\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\数据目录"; Filename: "{app}\data"; Tasks: datalinks
Name: "{group}\配置目录"; Filename: "{app}\configs"; Tasks: datalinks
Name: "{group}\输出目录"; Filename: "{app}\outputs"; Tasks: datalinks
Name: "{group}\配置文件"; Filename: "{app}\grace-l2.ini"; Tasks: datalinks
Name: "{group}\卸载 GRACE-L2"; Filename: "{uninstallexe}"

Name: "{autodesktop}\GRACE-L2"; Filename: "{app}\dist\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{autodesktop}\GRACE-L2 数据目录"; Filename: "{app}\data"; Tasks: desktopicon
Name: "{autodesktop}\GRACE-L2 配置目录"; Filename: "{app}\configs"; Tasks: desktopicon
Name: "{autodesktop}\GRACE-L2 输出目录"; Filename: "{app}\outputs"; Tasks: desktopicon

[Run]
Filename: "{app}\dist\{#MyAppExeName}"; Description: "启动 GRACE-L2"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"

[UninstallDelete]
; 只删除安装器生成的配置文件和空目录，不主动删除用户后续产生的数据成果。
Type: files; Name: "{app}\grace-l2.ini"

Type: dirifempty; Name: "{app}\outputs\local"
Type: dirifempty; Name: "{app}\outputs\remote"
Type: dirifempty; Name: "{app}\outputs\figures"
Type: dirifempty; Name: "{app}\outputs\logs"
Type: dirifempty; Name: "{app}\outputs"

Type: dirifempty; Name: "{app}\output\local"
Type: dirifempty; Name: "{app}\output\remote"
Type: dirifempty; Name: "{app}\output"

Type: dirifempty; Name: "{app}\configs"

Type: dirifempty; Name: "{app}\data\GRACE\GSM"
Type: dirifempty; Name: "{app}\data\GRACE\GIA"
Type: dirifempty; Name: "{app}\data\GRACE\LowDegree"
Type: dirifempty; Name: "{app}\data\GRACE"
Type: dirifempty; Name: "{app}\data\Hydro\GLDAS"
Type: dirifempty; Name: "{app}\data\Hydro\TRMM"
Type: dirifempty; Name: "{app}\data\Hydro"
Type: dirifempty; Name: "{app}\data\Reference\Mascon"
Type: dirifempty; Name: "{app}\data\Reference"
Type: dirifempty; Name: "{app}\data\Validation\TWSC_monthly"
Type: dirifempty; Name: "{app}\data\Validation"
Type: dirifempty; Name: "{app}\data\Boundary"
Type: dirifempty; Name: "{app}\data\DDK"
Type: dirifempty; Name: "{app}\data"

Type: dirifempty; Name: "{app}"

[Code]
function GetDefaultDir(Param: string): string;
begin
  if DirExists('D:\') then
    Result := '{#MyAppDefaultDir}'
  else
    Result := ExpandConstant('{autopf}\GRACE_L2');
end;
