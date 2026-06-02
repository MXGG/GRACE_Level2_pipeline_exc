# I/O Module

## Responsibility

**English**

`matlab/src/io/` defines output paths, product serialization, stack persistence, metadata writing, and log generation for the MATLAB backend.

**中文**

`matlab/src/io/` 负责 MATLAB 后端的输出路径定义、产品序列化、stack 持久化、元信息写入以及日志生成。

## Key Requirements

**English**

- Respect the shared local and remote output layout.
- Use safe-save patterns for large MAT outputs.
- Avoid writing the same large file from multiple workers.
- Keep stack orientation and metadata compatible with the Python backend.

**中文**

- 遵守本地与远程的统一输出目录规范。
- 对大型 MAT 输出采用安全保存模式。
- 避免多个 worker 同时写同一个大型文件。
- 保持 stack 方向和元信息与 Python 后端兼容。
