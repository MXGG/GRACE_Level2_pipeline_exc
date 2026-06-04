# Windows Packaging

Windows packaging is split by runtime.

## Python

Future canonical location:

```text
packaging/windows/python/
```

Expected assets:

```text
grace-l2-pipeline-vX.Y.Z-win-x64-setup.exe
grace-l2-pipeline-vX.Y.Z-win-x64-portable.zip
```

## MATLAB

Future canonical location:

```text
packaging/windows/matlab/
```

Use this directory for MATLAB Runtime notes or MATLAB batch wrappers if a compiled MATLAB runtime distribution is introduced.

## Installer

Future canonical location:

```text
packaging/windows/installer/
```

Inno Setup scripts and icons should be placed here, not in the repository root.
