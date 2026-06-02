# Inversion Module

## Responsibility

**English**

`matlab/src/inversion/` covers the Level-2 spherical harmonic path from monthly GSM coefficients to gridded equivalent water height. This includes monthly SH reading, low-degree replacement, mean-field handling, synthesis preparation, EWH synthesis, and optional GIA correction.

**中文**

`matlab/src/inversion/` 负责从月度 GSM 球谐系数到格网等效水高的整条 Level-2 反演路径，包括月度球谐读取、低阶项替换、均值场处理、合成准备、EWH 合成以及可选的 GIA 校正。

## Typical Files

| File | English | 中文 |
| --- | --- | --- |
| `inv_read_gsm_month.m` | Read one monthly GSM solution | 读取单个月度 GSM 解 |
| `inv_replace_low_degree.m` | Replace low-degree coefficients | 替换低阶项系数 |
| `inv_prepare_synthesis.m` | Prepare synthesis basis and weights | 准备合成基函数与权重 |
| `inv_synthesize_ewh_fast.m` | Synthesize EWH grid efficiently | 高效合成 EWH 格网 |
| `inv_apply_gia.m` | Apply GIA correction | 施加 GIA 校正 |

## Scientific Conventions

**English**

- Low-degree replacement should follow the shared RL06-style guidance used by both backends.
- Python and MATLAB must use the same replacement policy, month thresholds, and reference files.
- Output grids from inversion must remain compatible with the shared stack shape `[nLon x nLat x Nt]`.

**中文**

- 低阶项替换应遵循两端共用的 RL06 风格指导。
- Python 与 MATLAB 必须使用同一套替换策略、月份阈值和参考文件。
- 反演阶段输出的格网必须与共用 stack 维度 `[nLon x nLat x Nt]` 保持兼容。
