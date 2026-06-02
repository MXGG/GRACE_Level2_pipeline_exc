# HSAF 与 Stack 实现说明

本文档说明当前仓库中 HSAF 的两类科学策略、Python 侧实现入口、Stack 处理与存储逻辑，以及 2026-03-31 的本地性能结论。

## 1. 结论摘要

- 当前 HSAF 已经在 Python 中实现，不是运行时反复调用 MATLAB 接口。
- HSAF 的科学策略有两类：
  - 全局固定参数策略
  - 纬度自适应参数策略
- HSAF 的 Python 实现引擎目前有两类：
  - `engine=matlab_v3`：按 MATLAB 旧逻辑复写，目标是结果兼容
  - `engine=svd`：更轻量的纯 Python SVD/OLA 版本，速度更快，但结果需单独核验
- 当前主要瓶颈在 HSAF 计算，不在 Stack MAT 写盘。

## 2. `163 slices` 与 `158 slices` 的区别

这两个数字来自不同来源，不能混用：

- 当前默认配置的时间轴：
  - 由 `build_time_index(cfg)` 生成
  - 2026-03-31 本地核对结果：`Nt=163`
  - 时间范围：`2002-04 -> 2017-06`
- 我之前用于性能基准的旧 Stack 文件：
  - 文件：`G:\GRACE_Level2_pipeline_exc\output\local\stacks\P4M6_stack.mat`
  - 修改时间：`2026-03-23 19:21:30`
  - 文件内数据维度：`ewh.shape = (360, 180, 158)`

因此：

- 你看到日志里写 `1/163 slices processed` 是对的，代表当前运行计划的切片数。
- 我之前文档里写的 `158-slice`，只是因为基准测试直接拿了这个旧 `P4M6_stack.mat` 文件。
- 这个旧 stack 文件不是当前这次 `163 slices` 运行对应的产物。

补充核对：

- 当前 `output/local/monthly_mat/P4M6` 目录下有 `164` 个单月 MAT 文件。
- 当前默认时间轴是 `163` 个时间点。
- 旧 `P4M6_stack.mat` 则是 `158` 个时间层。

这说明本地现有产物里混有不同批次或不同时间索引逻辑下生成的结果，不能把它们直接当成同一次运行的严格对应物。

## 3. HSAF 的两种科学策略

### 3.1 全局固定参数策略

含义：

- 所有纬度带共享同一组 HSAF 参数。
- 典型参数为 `N / P / K / J / iterations`。
- 输入通常来自 `pre_hankel_input`，当前项目默认应为 `P4M6`。

MATLAB 参考脚本：

- `G:\GRACE_Level2_pipeline_exc\matlab\src\filters\HSAF_Global_V6Template_v3.m`

Python 对应入口：

- `G:\GRACE_Level2_pipeline_exc\python\grace_pipeline\filters\hsaf.py`
- 主要函数：`filter_grid_hsaf(...)`

### 3.2 纬度自适应参数策略

含义：

- 不同纬度带使用不同参数。
- 典型配置形式为：
  - `adaptive: [{lat_range: [...], params: {...}}, ...]`

MATLAB 参考脚本：

- `G:\GRACE_Level2_pipeline_exc\matlab\src\filters\filter_grid_hsaf_adaptive_profile.m`

Python 对应入口：

- `G:\GRACE_Level2_pipeline_exc\python\grace_pipeline\filters\hsaf.py`
- 主要函数：`filter_grid_hsaf_adaptive(...)`

## 4. Python 中的两层概念

当前 HSAF 在 Python 中有两层概念，必须区分：

### 4.1 科学策略层

- `variant=global`
- `variant=adaptive`

这决定参数是否随纬度变化。

### 4.2 工程实现层

- `engine=matlab_v3`
- `engine=svd`

这决定使用哪套 Python 代码执行。

当前建议：

- 若目标是尽量贴近 MATLAB 历史结果，优先使用 `engine=matlab_v3`。
- 若目标是做高速实验，可单独评估 `engine=svd`，但必须做结果核验。

## 5. HSAF 处理代码入口

### 5.1 HSAF 核心实现

文件：

- `G:\GRACE_Level2_pipeline_exc\python\grace_pipeline\filters\hsaf.py`

关键函数：

- `filter_grid_hsaf(...)`
- `filter_grid_hsaf_adaptive(...)`
- `filter_grid_hsaf_matlab(...)`
- `hsaf_global_filter_map_matlab(...)`
- `hsa_bidirectional_map(...)`
- `hsaf_1d(...)`
- `hsaf_1d_ola(...)`

### 5.2 Pipeline 中的 HSAF Stack 调度

文件：

- `G:\GRACE_Level2_pipeline_exc\python\grace_pipeline\app\pipeline.py`

关键函数：

- `_choose_hsaf_stack_workers(...)`
- `_choose_hsaf_outer_inner_workers(...)`
- `_prepare_hsaf_stack_config(...)`
- `_run_hsaf_stack_slice(...)`

关键逻辑：

- 月循环先生成 `RAW / GAUSS / P4M6 / DDK / FAN / ...` 等产品。
- 若 `stack_mode=true`，则先把 `pre_hankel_input` 对应产品累积成 3D Stack。
- 随后再对该 Stack 做 HSAF。
- 完成后可按需：
  - 保留在内存中
  - 写成 Stack MAT
  - 再回写为逐月 HSAF MAT

## 6. 当前并行策略

原始慢点不在于“并行核数少”，而在于并行层次放错了。

旧的低效方式：

- 单个 Python 进程里串行遍历整个 Stack
- 每个 slice 内部再开很多 worker

对 `engine=matlab_v3` 来说，这种做法很容易产生过度竞争，导致：

- `workers=20` 反而比 `workers=1` 更慢

当前改进后的思路：

- 小任务仍保留单进程整栈路径，避免进程启动开销。
- 大 Stack 改成“外层按 slice 多进程并行”。
- 内层 worker 不再盲目开大，而是按总 worker 预算分配。

因此现在会先计算：

- `outer_workers`
- `inner_workers`

再组合成：

- 外层 `ProcessPoolExecutor`
- 内层 HSAF 参数中的 `params["workers"]`

## 7. HSA 核心优化点

文件：

- `G:\GRACE_Level2_pipeline_exc\python\grace_pipeline\filters\hsaf.py`

函数：

- `hsa_bidirectional_map(...)`

近期已做的一项优化：

- 去掉了 forward/backward 两轮中的重复窗口计算。
- 现在先合并窗口起点，再统一处理。

效果：

- 不改变结果合同。
- 减少重复的 HSA/SVD/RC 计算量。

## 8. Stack 存储逻辑

### 8.1 存储入口

文件：

- `G:\GRACE_Level2_pipeline_exc\python\grace_pipeline\io\stack.py`

函数：

- `save_stack(...)`
- `load_stack(...)`
- `find_stack_file(...)`

### 8.2 当前存储格式

当前 Pipeline 标准输出仍以 MAT 为主，字段包括：

- `ewh`
- `lon`
- `lat`
- `t`
- `tag`

### 8.3 当前保存逻辑

`save_stack(...)` 的逻辑为：

1. 将 `ewh` 统一转换为连续 `float32`
2. 组装 MAT payload
3. 先写入 `*.tmp`
4. 再通过 `os.replace(...)` 原子替换正式文件

这样做的目的：

- 避免大文件写到一半时生成损坏目标文件
- 满足 Preview 对 MAT 文件的兼容要求

## 9. Preview 读取逻辑

文件：

- `G:\GRACE_Level2_pipeline_exc\python\grace_pipeline\infra\stack\loader.py`

关键函数：

- `load_stack_any(...)`
- `load_stack_slice_any(...)`

当前支持：

- MAT
- NetCDF / HDF5
- TXT

说明：

- Preview 并不只支持 MAT。
- 但为了兼容当前 GUI 和已有成果，Pipeline 主输出仍保持 MAT。
- `load_stack_slice_any(...)` 会尽量只读取单个时间片，避免为了预览单月而整栈读入。

## 10. 2026-03-31 本地性能实测

### 10.1 基准说明

本次性能基准使用的输入文件为：

- `G:\GRACE_Level2_pipeline_exc\output\local\stacks\P4M6_stack.mat`

注意：

- 该文件是旧产物。
- 它包含 `158` 个时间层，不代表当前默认配置的 `163` 个切片。

### 10.2 采样结果

对前 4 个 slice 的 HSAF 样本测试结果为：

- `outer_workers=4`
- `inner_workers=4`
- `hsaf_total_sec=55.023`
- `hsaf_avg_sec_per_slice=13.756`
- `save_4slice_stack_sec=0.003`
- `save_full_158slice_stack_sec=0.099`

结论：

- 当前已经不是 `60+s/slice` 这个量级。
- 真正慢的部分仍然是 HSAF 数值处理，不是 Stack MAT 写盘。

## 11. 对应代码文件总表

HSAF：

- `G:\GRACE_Level2_pipeline_exc\python\grace_pipeline\filters\hsaf.py`
- `G:\GRACE_Level2_pipeline_exc\python\grace_pipeline\app\pipeline.py`
- `G:\GRACE_Level2_pipeline_exc\matlab\src\filters\HSAF_Global_V6Template_v3.m`
- `G:\GRACE_Level2_pipeline_exc\matlab\src\filters\filter_grid_hsaf_adaptive_profile.m`

Stack 存储：

- `G:\GRACE_Level2_pipeline_exc\python\grace_pipeline\io\stack.py`
- `G:\GRACE_Level2_pipeline_exc\python\grace_pipeline\app\pipeline.py`

Preview 读取：

- `G:\GRACE_Level2_pipeline_exc\python\grace_pipeline\infra\stack\loader.py`
- `G:\GRACE_Level2_pipeline_exc\python\grace_pipeline\ui\qt\preview.py`
