# HSAF for GRACE Destriping: Theory, Algorithms, Validation, and Lessons Learned

## Executive Summary

This document summarizes the full research and engineering path explored in this project for applying Hankel Spectrum Analysis Filtering (HSAF) to GRACE/GRACE-FO destriping.

The key conclusions are:

1. The original HSAF idea, applied in the spatial grid domain, is meaningful as a signal decomposition method but not sufficient as a complete GRACE stripe solution.
2. The HSA paper shows that the real difficulty is not decomposition itself, but correct discrimination between signal modes and stripe/noise modes.
3. The GRACE stripe literature, especially the Peidou line of work, indicates that the dominant stripe component is not generic random high-frequency noise. It is better interpreted as a structured pseudo-moire or sub-Nyquist artifact tied to orbit sampling geometry and monthly ground-track bundles.
4. This explains why many post-processing ideas that look reasonable on the final EWH map fail in practice: they are acting too late, after the critical sampling structure has already been mixed into the recovered field.
5. A large set of prototype methods were implemented and tested in code. Most of them failed to outperform the current project HSAF, and none of them outperformed DDK4 as an engineering destriping baseline.
6. The most important outcome of this phase is therefore not a new winning filter, but a systematic narrowing of what does not work, and a clearer definition of what the next-generation method should look like.

The recommended next stage is a physically grounded sampling-aware inversion-side formulation, ideally closer to SH residual formation or the inversion operator itself, with HSA used only after a stripe-relevant subspace has been isolated.

## 中文执行摘要

本文档系统整理了本项目中将 HSAF 用于 GRACE/GRACE-FO 去条带滤波的完整研究与实现过程，包括理论依据、算法设计、代码实验、结果验证以及经验总结。

核心结论如下：

1. 现有空间域 HSAF 从信号分解角度是有意义的，但它并不足以单独解决 GRACE 条带问题。
2. HSA 理论本身强调的关键不是“分解”动作，而是“如何可靠地区分真实信号模态与条带噪声模态”。
3. 根据 Peidou 关于 GRACE 条带的论文，GRACE 南北条带的主导部分并不是普通高频随机噪声，而更接近由轨道采样几何、月度 ground-track bundle 和低频背景共同作用形成的 pseudo-moire / sub-Nyquist 结构化伪影。
4. 这也解释了为什么很多在最终 EWH 图上看起来合理的后处理策略会失败：真正决定条带结构的信息，在球谐反演并形成月度格网之后，已经部分丢失或与真实信号严重缠绕。
5. 本轮工作中已经实际实现并测试了大量原型方法，包括空间域自适应 HSA、SH 域 HSA、轨道模板驱动的后处理、pseudo-moire 代理算子以及第一版 sampling-aware inversion-side prototype；这些方法均未超过当前项目 HSAF，更没有超过 DDK4 的工程稳健性。
6. 因此，本阶段最重要的成果不是“找到更好的滤波器”，而是较系统地验证了“哪些看起来合理的 HSA 扩展方法为什么不行”，并把下一阶段研究方向收敛到更靠前的 sampling-aware inversion-side 框架。

一句话概括：  
如果未来还要继续把 HSA 用于 GRACE 去条带，它更应该作为“物理采样约束子空间中的辅助分解工具”，而不是直接作为最终 EWH 图上的主滤波器。

## 1. Scope and Goal

This document covers four tightly linked topics:

1. the theoretical basis of HSA and why it looked promising for GRACE stripe suppression;
2. the physical interpretation of GRACE stripes from the orbit-sampling literature;
3. the concrete algorithm branches implemented in this repository;
4. the validation results and what they imply for future method design.

The purpose is not only to list experiments, but to connect theory, implementation, and failure modes into one coherent research record.

## 2. Reference Basis

### 2.1 HSA theory

- Shi et al., *Hankel Spectrum Analysis: A Decomposition Method for Quasi-Periodic Signals and Its Applications*  
  Local file:  
  `C:\Users\LX1\Desktop\Documents&Sheets&Slides\Postgraduate Thesis\References\JGR Solid Earth - 2023 - Shi - Hankel Spectrum Analysis  A Decomposition Method for Quasi-Periodic Signals and Its-3-6.pdf`

### 2.2 User-side HSAF / thesis reference

- Local file:  
  `C:\Users\LX1\Desktop\Documents&Sheets&Slides\Postgraduate Thesis\References\1-s2.0-S0022169425019420-main.pdf`

### 2.3 GRACE stripe and pseudo-moire references

- Peidou et al., *Stripe Mystery in GRACE Geopotential Models Revealed*  
  `G:\HSAF\Paper\References\Geophysical Research Letters - 2020 - Peidou - Stripe Mystery in GRACE Geopotential Models Revealed.pdf`
- Remote Sensing discussion of stripy components and sub-Nyquist artifacts  
  `G:\HSAF\Paper\References\remotesensing-13-04362-v2 (1).pdf`
- Peidou doctoral dissertation  
  `G:\HSAF\Paper\References\Peidou_Athina_2020_PhD.pdf`

### 2.4 GRACE Level-2 inversion / filtering references already aligned in this codebase

- [SH_INVERSION_REFERENCE_NOTES.md](/G:/GRACE_Level2_pipeline_exc/docs/SH_INVERSION_REFERENCE_NOTES.md)

These include:

- Wahr et al. (1998)
- CSR RL06 / RL06.3 notes
- TN-13 geocenter replacement
- TN-14 C20/C30 replacement
- Swenson and Wahr (2006)
- Kusche (2007)

## 3. Theoretical Basis

### 3.1 What HSA assumes

HSA assumes that a one-dimensional sequence can be approximated as a sum of quasi-periodic or exponentially modulated modes:

```text
x(t) ≈ Σ[k=1..K] A_k * exp(alpha_k * t) * cos(2*pi*f_k*t + phi_k)
```

where each mode has:

- amplitude \(A_k\)
- damping or growth factor \(\alpha_k\)
- frequency \(f_k\)
- phase \(\phi_k\)

The sequence is embedded into a Hankel matrix:

```text
H =
[ x1       x2       ... xP     ]
[ x2       x3       ... xP+1   ]
[ ...      ...      ... ...    ]
[ xN-P+1   xN-P+2   ... xN     ]
```

In words, each row is a shifted copy of the original sequence, and each anti-diagonal contains the same original sample.  
This is the structure that lets oscillatory content become a low-rank or approximately low-rank component in the embedded space.

Then SVD / subspace methods are used to recover modal structure. In practical terms:

1. build Hankel embedding;
2. estimate dominant subspace;
3. derive modal poles or equivalent modal basis;
4. reconstruct selected modes only.

### 3.2 Why this looked attractive for GRACE

The original intuition was:

- GRACE stripe patterns often appear as oscillatory structures along latitude circles;
- such oscillatory behavior could be represented by a small set of stripe-like modes;
- if those modes could be separated from true hydrological signal modes, HSA could become a selective destriping tool rather than a blunt smoothing filter.

### 3.3 The critical limitation

The HSA paper itself implies that decomposition is only half the problem. The real challenge is the decision rule:

- which modes are signal?
- which modes are stripe/noise?
- which modes are mixed?

If that discrimination step is physically wrong, HSA will not help.

## 4. What the GRACE Stripe Papers Imply

### 4.1 Conventional but incomplete interpretation

A naive interpretation is:

- stripes are just high-frequency noise;
- therefore they can be removed by deleting high-frequency or weak-energy modes.

The experiments in this project, together with the Peidou literature, show that this is not enough.

### 4.2 Peidou-style interpretation

The more realistic interpretation is:

- GRACE stripes are strongly related to orbit sampling geometry;
- they are linked to monthly ground-track bundles;
- they behave like structured pseudo-moire / sub-Nyquist artifacts;
- visually they look north-south elongated, but dynamically they behave as quasi-periodic oscillations along latitude circles;
- the stripe field changes with month because the bundle geometry and phase change with month.

This changes the modeling problem from:

- "find high-frequency noise"

to:

- "identify a structured sampling artifact generated by bundle geometry acting on a low-frequency carrier and the inversion process."

### 4.3 Consequence for algorithm design

A good destriping method must somehow encode:

- directionality;
- monthly bundle dependence;
- interaction with low-order carrier structure;
- separation between signal-preserving and stripe-suppressing operations.

This is exactly why many purely map-domain post-filters failed.

## 5. Original HSAF in This Project

### 5.1 Baseline implementation

Primary files:

- [hsaf.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/filters/hsaf.py)
- MATLAB reference under `matlab/src/filters/`

The baseline pipeline behavior retained during all experiments:

- HSAF default input: `P4M6`
- current production engine path aligned to the existing project baseline
- stack-mode filtering of monthly slices

### 5.2 Baseline idea

For each latitude-oriented or local spatial profile:

1. form a Hankel matrix;
2. decompose into modes;
3. suppress stripe-like content using fixed or semi-fixed modal rules;
4. reconstruct filtered grid.

### 5.3 Why it remains useful

- computationally workable after optimization;
- preserves some broad hydrological structures;
- acceptable on moderate months;
- better than many later prototypes.

### 5.4 Why it remains insufficient

- bad months retain strong stripe residuals;
- mode selection is too rigid;
- global parameters do not follow monthly stripe variability;
- no explicit orbit-sampling model is embedded.

## 6. Validation Design Used in This Work

### 6.1 Representative months

All prototype branches were evaluated on the same four months:

- `2002-04` : severe early bad month
- `2007-05` : relatively good middle month
- `2015-09` : stripe-heavy month
- `2017-03` : very bad late month

### 6.2 Comparison baseline

Every prototype was compared against:

- current project HSAF output
- same-month `DDK4`

`DDK4` was not treated as perfect truth, but as a stable engineering reference for stripe suppression.

### 6.3 Metrics

For each month and method:

- `RMSE` relative to DDK4
- correlation relative to DDK4
- `ocean anisotropy index`
- `ocean stripe-band energy`
- `land variance retention`

### 6.4 Experiment infrastructure

Runner:

- [hsaf_experiments.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/app/hsaf_experiments.py)

CLI:

- [cli.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/cli.py)

Result root:

- `G:\GRACE_Level2_pipeline_exc\output\local\compare\hsaf_experiments`

## 7. Real Orbit Data Infrastructure Added

To move beyond heuristic stripe guesses, real GRACE Level-1B orbit data was fetched and parsed.

Main files:

- [grace_l1b_fetch.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/app/grace_l1b_fetch.py)
- [grace_groundtrack.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/app/grace_groundtrack.py)

Implemented capabilities:

- GFZ Level-1B download and extraction
- `GNV1B` parsing
- monthly ground-track density construction
- bundle template generation
- phase template generation
- bundle-derived order risk score generation

This allowed later methods to use actual monthly orbit geometry rather than synthetic stripe assumptions.

## 8. Prototype Families

This section records each major experimental branch, including design angle, theoretical basis, implementation detail, representative pseudocode, and observed failure mode.

### 8.1 Family A: Grid-domain adaptive modal scoring

Implemented engines:

- `modal_adaptive_v1`
- `modal_adaptive_latband_v1`
- `multichannel_v1`
- `modal_adaptive_v2`, `modal_adaptive_latband_v2`, `multichannel_v2`
- `modal_adaptive_v3`, `modal_adaptive_latband_v3`, `multichannel_v3`

Primary file:

- [hsaf.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/filters/hsaf.py)

#### Design angle

Stay in the spatial grid domain, but replace fixed modal deletion with adaptive modal scoring.

#### Theoretical basis

- follows HSA's modal logic;
- tries to classify stripe-like modes from mode attributes;
- later versions inject stripe-band and neighborhood information.

#### Core algorithm idea

For each spatial window:

1. build Hankel matrix from profile;
2. decompose into modes;
3. compute stripe score from mode features;
4. attenuate modes softly instead of hard deletion;
5. reconstruct the profile.

#### Representative scoring logic

```text
stripe_score =
    w1 * band_score
  + w2 * persistence
  + w3 * ocean_bias
  + w4 * anisotropy
  + w5 * pole_or_energy_aux

attenuation = min(0.85, stripe_score^1.5)
```

#### Representative pseudocode

```text
for each latitude profile:
    for each sliding window:
        H = hankel_embed(profile_window)
        modes = decompose(H)
        for each mode:
            score = stripe_score(mode)
            mode = (1 - attenuation(score)) * mode
        reconstruct window
average overlapping reconstructions
```

#### Main problem encountered

- the scoring rules were not physically specific enough;
- signal-like and stripe-like modes remained mixed;
- bad months stayed bad;
- real signal was frequently over-attenuated.

#### Representative result directories

- `20260402_224207`
- `20260403_125220`
- `20260403_133618`

### 8.2 Family B: Carrier-removed grid-domain HSAF

Implemented engines:

- `carrier_removed_hsaf_v1`
- `carrier_removed_multichannel_v1`

Primary file:

- [hsaf_experiments.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/app/hsaf_experiments.py)

#### Design angle

Remove a low-order carrier grid first, then run HSAF only on the residual field.

#### Theoretical basis

- motivated by pseudo-moire thinking: stripe artifacts may be clearer in the high-frequency residual than in the full field.

#### Representative pseudocode

```text
(C, S) = monthly SH coefficients
carrier = low-order synthesis(C, S, L<=Lc, m<=mc)
residual = grid_input - carrier
filtered_residual = HSAF(residual)
output = carrier + filtered_residual
```

#### Main problem encountered

- carrier removal alone did not isolate stripe structure;
- the remaining residual still contained mixed signal and stripe contributions;
- HSA on the residual was still not selective enough.

#### Representative result directory

- `20260403_170500_carrier_p4m6`

### 8.3 Family C: SH-domain HSA and SH-domain demodulation

Implemented engines:

- `sh_orderwise_v1`
- `sh_multichannel_v1`
- `sh_demod_v1`
- `sh_demod_multichannel_v1`

Primary file:

- [hsaf_sh.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/filters/hsaf_sh.py)

#### Design angle

Move decomposition from map space to spherical harmonic coefficient space.

#### Theoretical basis

- DDK works in the SH space;
- stripes might be easier to identify along degree sequences or order-wise structures;
- demodulation was added to extract narrow-band oscillatory content in coefficient sequences.

#### Representative pseudocode

```text
for each order m:
    split even and odd degree sequences
    if orderwise:
        modes = HSA(seq_degree)
        attenuate stripe-like modes
    if demod:
        residual = seq - lowpass(seq)
        band = bandpass(residual)
        baseband = analytic(band) * exp(-i*2*pi*f*n)
        clean baseband and remodulate
reconstruct filtered Cnm/Snm
```

#### Main problem encountered

- simple order-wise or parity-wise processing did not capture true stripe generation;
- multichannel coupling across orders was too weak;
- SH post-filtering without the correct sampling model was still too late.

#### Representative result directories

- `20260403_154514`
- `20260403_155200_p4m6_sh`
- `20260403_162500_sh_demod_p4m6`

### 8.4 Family D: Real orbit bundle templates in the grid domain

Implemented engines:

- `orbit_bundle_v1`
- `orbit_bundle_multichannel_v1`
- `bundle_phase_demod_v1`
- `bundle_phase_demod_multichannel_v1`

Primary files:

- [grace_groundtrack.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/app/grace_groundtrack.py)
- [hsaf_experiments.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/app/hsaf_experiments.py)

#### Design angle

Use actual monthly GRACE L1B orbit data to construct bundle density and phase templates, then use those templates for stripe suppression.

#### Theoretical basis

- directly inspired by Peidou's monthly ground-track bundle interpretation;
- attempts to replace generic stripe heuristics with actual orbit-driven structures.

#### Representative pseudocode

```text
bundle_density = monthly_groundtrack_density(month)
bundle_template = bandpass_and_smooth(bundle_density)
residual = input_grid - lowpass(input_grid)
for each latitude:
    fit residual_band onto bundle_template row
    subtract fitted stripe component
```

Phase-aware version:

```text
phase_unit = normalize_analytic_phase(bundle_template)
baseband = analytic(residual_band) * conj(phase_unit)
clean baseband
reconstruct cleaned_band = baseband_clean * phase_unit
```

#### Main problem encountered

- real orbit geometry improved physical relevance but not performance;
- template projection on the final map still behaved like a late correction;
- phase-aware demodulation improved interpretation more than actual filtering quality.

#### Representative result directories

- `20260403_181500_orbit_bundle_p4m6`
- `20260403_183500_bundle_phase_demod_p4m6`

### 8.5 Family E: Orbit-aware SH-domain prototypes

Implemented engines:

- `sh_orbit_orderwise_v1`
- `sh_orbit_multichannel_v1`
- `sh_orbit_demod_v1`
- `sh_orbit_demod_multichannel_v1`
- `sh_orbit_carrier_demod_v1`
- `sh_orbit_carrier_demod_multichannel_v1`

Primary files:

- [hsaf_sh.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/filters/hsaf_sh.py)
- [hsaf_experiments.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/app/hsaf_experiments.py)

#### Design angle

Use monthly orbit-derived bundle information to build `order` risk scores, then inject these scores into SH-domain HSA and demodulation branches.

Later versions first removed low-order carrier in SH space.

#### Theoretical basis

- tries to merge Peidou's orbit/bundle insight with SH-domain filtering;
- assumes monthly dangerous orders can be inferred from real bundle templates.

#### Representative pseudocode

```text
bundle_template = build_from_L1B(month)
order_scores = bundle_to_order_spectrum(bundle_template)
for each order m:
    risk = order_scores[m]
    apply HSA or demod cleaning with gain scaled by risk
```

Carrier-removed variant:

```text
(Ccar, Scar, Cres, Sres) = split_low_order_carrier(C, S)
clean (Cres, Sres) with orbit-aware SH demodulation
output = (Ccar + Cres_clean, Scar + Sres_clean)
```

#### Main problem encountered

- orbit-derived order weighting alone was too weak;
- even carrier splitting did not solve the problem;
- the true coupling between sampling geometry and stripe formation is more than simple order weighting.

#### Representative result directories

- `20260403_191500_sh_orbit_bundle`
- `20260403_193200_sh_orbit_carrier`

### 8.6 Family F: Pseudo-moire / sampling-operator proxies on the final map

Implemented engines:

- `pseudo_moire_operator_v1`
- `pseudo_moire_operator_multichannel_v1`
- `sampling_operator_v1`
- `sampling_operator_multichannel_v1`

Primary file:

- [hsaf_experiments.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/app/hsaf_experiments.py)

#### Design angle

Construct a richer final-map pseudo-moire subspace using:

- bundle template;
- quadrature/phase component;
- low-order carrier;
- carrier derivative;
- interaction terms between these fields.

Then use constrained ridge regression to estimate and subtract stripe residual.

#### Representative pseudocode

```text
template = bundle_template(month)
quad = hilbert_imag(template)
carrier = low_order_carrier_grid
dcarrier = d/dlon carrier
design = [
    template,
    quad,
    carrier*template,
    carrier*quad,
    dcarrier*template,
    dcarrier*quad
]
fit design to residual_band in ocean-weighted least squares
subtract fitted stripe estimate
```

#### Main problem encountered

- after full EWH formation, the stripe artifact and the real field are too entangled;
- the richer proxy basis still collapsed numerically to nearly the same result as simple template projection;
- no substantial new recoverable information was exposed in the final map domain.

#### Representative result directories

- `20260403_200200_pseudo_moire`
- `20260403_201200_sampling_operator`

### 8.7 Family G: First inversion-side sampling-aware prototype

Implemented engines:

- `sampling_inversion_v1`
- `sampling_inversion_multichannel_v1`

Primary file:

- [sampling_aware.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/inversion/sampling_aware.py)

#### Design angle

Move the prototype into inversion-side SH residual regularization.

This was the first branch that was no longer just a post-processing map filter.

#### Theoretical basis

- if stripes are sampling-related, then the operator should act earlier than final-map correction;
- high-order SH residuals can be regularized according to monthly orbit-risk information.

#### Core algorithm

1. split low-order SH carrier from total field;
2. compute monthly orbit order scores from real bundle template;
3. regularize high-order residual sequences using:
   - degree second-difference penalty;
   - optional neighboring-order coupling;
   - risk-scaled regularization strength;
4. reconstruct filtered SH field.

#### Representative equations

For a residual sequence `x`, the first inversion-side prototype solves a regularized problem of the form:

```text
x_hat = argmin over x:

    ||x - x0||^2
  + lambda_degree  * risk[m] * ||D2 x||^2
  + lambda_neighbor * risk[m] * ||x - x_neighbor||^2
```

where:

- `x0` is the original residual sequence
- `D2` is the second-difference operator in degree
- `x_neighbor` is a neighboring-order residual sequence
- `risk[m]` is the monthly orbit-derived risk for order `m`

#### Representative pseudocode

```text
(Ccar, Scar, Cres, Sres) = split_low_order_carrier(C, S)
order_scores = monthly_bundle_to_order_scores(month)
for each order m and parity group:
    x0 = residual_sequence(Cres or Sres)
    xneighbor = neighboring_order_sequence()
    xhat = solve(
        ||x-x0||^2
        + lambda_degree * risk[m] * ||D2 x||^2
        + lambda_neighbor * risk[m] * ||x-xneighbor||^2
    )
    replace residual sequence with xhat
reconstruct SH and synthesize EWH
```

#### Main problem encountered

- this first inversion-side version still behaves like a risk-weighted smoother;
- it does not yet encode the actual pseudo-moire forward coupling mechanism;
- neighboring-order coupling added little practical benefit.

#### Representative result directory

- `20260404_101500_sampling_inversion`

## 9. Representative Results

### 9.1 Current baseline used in all comparisons

Current project HSAF relative to DDK4:

| Month | RMSE vs DDK4 |
|---|---:|
| 2002-04 | 34.31 |
| 2007-05 | 9.65 |
| 2015-09 | 37.21 |
| 2017-03 | 56.58 |

This baseline is imperfect, but it remained better than nearly all prototypes tested.

### 9.1.1 Visual baseline summary

The following figures make the baseline situation more concrete.

Current HSAF vs DDK4 monthly scan:

![Current HSAF vs DDK4 monthly scan](../output/local/compare/hsaf_vs_ddk4_month_scan/timeseries.png)

Figure note: This panel summarizes how the current project HSAF compares with DDK4 across all months. It is useful for identifying bad-month clusters, rather than judging absolute truth.

Python-vs-MATLAB HSAF parity summary:

![Python vs MATLAB HSAF parity summary](../output/local/compare/193974_vs_193977/selected_month_summary.png)

Figure note: This summary confirms that after parity corrections, Python and MATLAB HSAF outputs are already very close, so later failures are algorithmic rather than platform-consistency issues.

### 9.2 Representative prototype outcomes

| Family / Engine | 2002-04 | 2007-05 | 2015-09 | 2017-03 | General verdict |
|---|---:|---:|---:|---:|---|
| `modal_adaptive_v1` | 61.83 | worse than baseline | worse | 86.21 | failed |
| `modal_adaptive_latband_v1` | slightly steadier than v1 | still worse | still worse | still worse | failed |
| `sh_orderwise_v1` | 146.37 or 52+ depending on input branch | much worse | worse | very bad | failed |
| `orbit_bundle_v1` | 89.46 | 33.85 | 58.74 | 109.03 | failed |
| `bundle_phase_demod_v1` | 61.39 | 23.17 | 54.06 | 90.72 | failed |
| `sh_orbit_orderwise_v1` | 123.83 | 52.68 | 67.59 | 402.31 | failed badly |
| `sh_orbit_carrier_demod_v1` | 96.18 | 52.49 | 68.46 | 113.59 | failed |
| `pseudo_moire_operator_v1` | 89.46 | 33.85 | 58.74 | 109.03 | failed |
| `sampling_inversion_v1` | 100.36 | 52.99 | 67.83 | 114.80 | failed |

The common pattern is clear:

- all major branches remained worse than the current HSAF baseline;
- all major branches remained worse than DDK4;
- no branch achieved the target of improving severe months while preserving good months.

### 9.3 Embedded experiment figures

#### 9.3.1 Grid-domain adaptive-modal family

![modal adaptive summary](../output/local/compare/hsaf_experiments/20260402_224207/summary_metrics.png)

This figure shows that simply replacing fixed mode deletion with adaptive modal scoring does not solve the severe-month problem.
Figure note: The bad-month metrics remain much worse than the current HSAF baseline, indicating that modal scoring alone is not a sufficient physical discriminator.

#### 9.3.2 Raw-input residual-first family

![raw residual-first summary](../output/local/compare/hsaf_experiments/20260403_125220/summary_metrics.png)

This branch showed that using `RAW` as the direct input generally made the stripe problem harder rather than easier.
Figure note: This result supports keeping `P4M6` as the preferred HSAF input route in the current pipeline.

#### 9.3.3 Template-gated / v3 family

![template-gated v3 summary](../output/local/compare/hsaf_experiments/20260403_133618/summary_metrics.png)

This branch indicates that adding template gating on top of HSA scoring did not produce a stable separation between stripe and signal modes.
Figure note: Even with stronger gating, the model still damages good months and does not rescue the bad months.

#### 9.3.4 SH-domain demodulation family

![sh demod summary](../output/local/compare/hsaf_experiments/20260403_162500_sh_demod_p4m6/summary_metrics.png)

The SH-domain branch confirms that moving decomposition into degree-order space alone is not enough.
Figure note: This was an important negative result because it showed that simply changing domain, without changing the physical model, does not solve the stripe problem.

#### 9.3.5 Real-orbit bundle-template family

![orbit bundle summary](../output/local/compare/hsaf_experiments/20260403_181500_orbit_bundle_p4m6/summary_metrics.png)

![bundle phase demod summary](../output/local/compare/hsaf_experiments/20260403_183500_bundle_phase_demod_p4m6/summary_metrics.png)

These figures show that adding real orbit bundle geometry at the final-map stage improved physical interpretation more than actual filtering quality.
Figure note: These runs were the first ones to use real monthly GRACE L1B-derived bundle geometry, but the benefits remained interpretive rather than performance-driven.

#### 9.3.6 Orbit-aware SH family

![sh orbit summary](../output/local/compare/hsaf_experiments/20260403_191500_sh_orbit_bundle/summary_metrics.png)

![sh orbit carrier summary](../output/local/compare/hsaf_experiments/20260403_193200_sh_orbit_carrier/summary_metrics.png)

These results indicate that orbit-derived order weighting by itself is not the missing ingredient.
Figure note: Removing low-order carrier before orbit-aware SH demodulation still did not recover a useful stripe/signal separation mechanism.

#### 9.3.7 Pseudo-moire proxy and sampling-operator proxy families

![pseudo moire summary](../output/local/compare/hsaf_experiments/20260403_200200_pseudo_moire/summary_metrics.png)

![sampling operator summary](../output/local/compare/hsaf_experiments/20260403_201200_sampling_operator/summary_metrics.png)

These two branches nearly collapsed to the same result, showing that the proxy basis on the final map still did not capture the true coupling mechanism.
Figure note: This collapse is itself informative: adding more proxy terms in the final-map stage did not create a genuinely richer identifiable stripe subspace.

#### 9.3.8 First inversion-side sampling-aware family

![sampling inversion summary](../output/local/compare/hsaf_experiments/20260404_101500_sampling_inversion/summary_metrics.png)

This figure is important because it shows that even after moving earlier into SH residual regularization, the first inversion-side prototype remained too weak and still behaved like a smoother.
Figure note: This is the first branch that genuinely moved the logic earlier than map-domain post-processing, but it still lacked an explicit pseudo-moire forward operator.

### 9.4 How to read these figures

In the summary figures:

- a lower `RMSE vs DDK4` is better;
- a higher `corr vs DDK4` is better;
- a lower `ocean anisotropy` usually means less stripe contamination;
- a lower `ocean stripe-band energy` usually means less stripe-band residual;
- `land retention` should not collapse, otherwise the method is over-smoothing the real signal.

### 9.5 Method comparison table

| Family | Domain | Main physical assumption | Main implementation idea | Typical outcome | Main problem |
|---|---|---|---|---|---|
| Original HSAF | grid domain | stripe is separable in spatial profiles | Hankel decomposition and fixed or semi-fixed modal suppression | workable baseline | bad months still fail |
| Adaptive modal HSA | grid domain | stripe modes can be identified by scored modal features | stripe-score and soft attenuation | worse than baseline | modal labeling remained heuristic |
| Carrier-removed HSA | grid residual | stripe is clearer after low-order carrier removal | remove carrier then run HSA | no stable gain | residual still mixes signal and stripe |
| SH HSA | SH domain | stripe is easier to isolate along degree-order sequences | order-wise or parity-wise HSA | worse than baseline | missing real sampling coupling |
| Orbit bundle template | final map | stripe shape can be projected from monthly bundle template | regress final-map residual on real orbit template | worse than baseline | orbit info added too late |
| Phase-demod bundle | final map | stripe is a narrow-band modulated component | demodulate by bundle phase then clean baseband | slightly more interpretable but still worse | still acts after map formation |
| Orbit-aware SH HSA | SH domain | dangerous orders can be inferred from bundle geometry | use monthly orbit-order weights in SH HSA | failed badly on bad months | order weighting alone too weak |
| Pseudo-moire proxy | final map | final stripe field can be expressed by template-carrier interactions | constrained regression on proxy basis | collapsed to template projection | not enough recoverable information left |
| Sampling-aware inversion v1 | inversion-side SH residual | residual can be regularized using orbit risk | degree regularization + neighbor-order coupling | still worse than baseline | still only a smoother, not a forward model |

## 10. Why These Methods Failed

### 10.1 Failure mode 1: wrong object of separation

Many methods assumed that stripe noise is already a separable component on the final EWH map.  
The experiments indicate this is often false.

### 10.2 Failure mode 2: HSA without physically correct modal labeling

HSA gives a decomposition, but not a guaranteed physical interpretation.  
Without the right stripe-generation model, adaptive modal scoring remains heuristic.

### 10.3 Failure mode 3: orbit information added too late

Real orbit bundle information was added, but mostly after inversion and synthesis.  
At that stage, the artifact is already too entangled with the signal field.

### 10.4 Failure mode 4: regularization is not the same as forward modeling

The first inversion-side prototype still used a smoothing-style regularizer.  
It did not yet build a true sampling-aware forward operator.

### 10.5 Failure mode 5: the missing coupling mechanism

The repeated failure across:

- grid-domain adaptive HSA,
- SH-domain orderwise HSA,
- orbit-template projection,
- phase demodulation,
- pseudo-moire proxy operators,
- and the first inversion-side regularizer

indicates that the real missing piece is not simply better weights, better scoring, or stronger smoothing.

The missing piece is the coupling mechanism:

```text
monthly orbit sampling geometry
    + low-order carrier / background field
    + inversion / residual formation
        -> structured pseudo-moire stripe field
```

Until this coupling is represented explicitly, later-stage methods remain underinformed.

## 11. What Was Learned About Using HSA for GRACE

### 11.1 HSA is still useful, but not in the naive way

HSA may still play a role in GRACE destriping if used:

- after the physically relevant stripe subspace has been isolated;
- on inversion residual components rather than final maps;
- as a local decomposition or mode interpretation tool, not as a universal final-map filter.

### 11.2 What HSA should probably not be asked to do

HSA alone should not be expected to:

- discover the entire GRACE stripe mechanism from final maps;
- fully replace DDK/P4M6-like engineering filters;
- infer orbit-induced pseudo-moire coupling without an explicit sampling model.

### 11.3 Reinterpreting the role of HSA in GRACE

The experiments suggest that HSA should be repositioned conceptually:

```text
not:
    final EWH map -> HSA -> stripe/signal separation

but:
    sampling-aware operator or stripe-relevant residual extraction
        -> HSA decomposition inside that reduced subspace
        -> selective mode interpretation or attenuation
```

This is a narrower role, but it is much more consistent with both the HSA theory and the GRACE stripe literature.

## 12. Recommended Next Step

The next serious branch should be a genuine sampling-aware forward or inverse operator, not another late post-filter.

The target structure should include:

1. monthly bundle geometry from real L1B tracks;
2. explicit carrier-modulation coupling in SH or inversion space;
3. a pseudo-moire basis or operator generated before final EWH synthesis;
4. optional HSA applied only after that operator isolates a stripe-relevant residual component.

### 12.1 Proposed second-generation prototype architecture

The next serious prototype should look more like:

```text
Level-2 monthly SH coefficients
    -> low-degree replacement / mean removal / GIA
    -> split low-order carrier and high-order residual
    -> derive monthly bundle geometry from real L1B tracks
    -> build SH-space pseudo-moire basis from bundle-carrier coupling
    -> solve constrained inversion / projection in that basis
    -> optionally apply HSA only to the isolated stripe-relevant residual
    -> reconstruct SH field
    -> synthesize EWH
```

This would be qualitatively different from all the prototype families already tested, because the key coupling mechanism would be introduced before final-map synthesis.

## 13. Discussion

### 13.1 Why DDK4 remained strong throughout

DDK4 is not derived from the same pseudo-moire interpretation as the Peidou literature, but it consistently remained the strongest engineering baseline in these experiments.

The likely reasons are:

- it operates in a domain where correlated GRACE errors are naturally organized;
- it suppresses structured noise robustly without requiring explicit monthly identification of stripe modes;
- it does not rely on a fragile signal-versus-stripe modal classification step.

This does not mean DDK4 is theoretically complete. It means that, at the current stage, its bias-variance tradeoff is still better than the tested HSA-derived variants.

### 13.2 Why the Peidou interpretation still matters even though the prototypes failed

The failure of the prototypes does not contradict the Peidou literature. It supports it.

If the dominant stripe field is genuinely tied to sampling geometry and pseudo-moire behavior, then post-processing on the final EWH map should be expected to struggle. That is exactly what was observed:

- adding more modal sophistication did not solve the problem;
- adding real orbit templates did not solve the problem;
- moving to SH-domain smoothing still did not solve the problem.

This pattern is consistent with the idea that the key information has to be introduced before final map synthesis.

### 13.3 Why the first inversion-side prototype still underperformed

The first inversion-side prototype moved the experiment earlier, which was the correct directional shift, but it still underperformed because it remained a regularization scheme rather than a generative model.

In practical terms, it answered this question:

```text
which coefficients should be smoothed more because bundle risk is high?
```

But the harder and more relevant question is:

```text
how does monthly sampling geometry transform low-order background structure into the observed stripe residual?
```

Until the second question is modeled directly, the method remains underpowered.

### 13.4 What would count as a real breakthrough

A genuinely promising next-generation method would need at least one of the following:

- a sampling-aware operator that maps bundle geometry and carrier structure into an expected pseudo-moire residual basis;
- a reduced inversion model where stripe-relevant degrees/orders are solved jointly with a structured artifact basis;
- an HSA stage applied only after the artifact-bearing residual space has already been isolated by physics-informed constraints.

In other words, the breakthrough is unlikely to come from a better heuristic filter. It is more likely to come from a better forward model.

## 14. Experiment Timeline and Audit Trail

This section records the main experiment branches in roughly chronological order, together with the corresponding output folders and the practical conclusion drawn from each round.

### 14.1 Early grid-domain modal families

- `20260402_223041`
  - early small-sample experiment batch
  - established the basic experiment runner and comparison workflow
- `20260402_224207`
  - `modal_adaptive_v1`, `modal_adaptive_latband_v1`, `multichannel_v1`
  - conclusion: adaptive modal scoring alone did not beat the current HSAF

### 14.2 Raw-input and stronger gating families

- `20260403_125220`
  - `RAW + v2` family
  - conclusion: using RAW directly made the stripe problem harder
- `20260403_133618`
  - `v3` template-gated family
  - conclusion: gating on top of modal scoring still failed to separate stripe and signal reliably

### 14.3 SH-domain decomposition families

- `20260403_154514`
  - first SH-domain HSA batch
  - conclusion: simple SH-domain orderwise decomposition underperformed
- `20260403_155200_p4m6_sh`
  - SH-domain tests on `P4M6` input
  - conclusion: domain change alone was not enough
- `20260403_162500_sh_demod_p4m6`
  - SH-domain demodulation family
  - conclusion: demodulation in SH space still failed without the correct sampling model

### 14.4 Carrier-splitting and orbit-template families

- `20260403_170500_carrier_p4m6`
  - carrier-removed grid-domain hybrid
  - conclusion: low-order carrier removal alone did not isolate stripe structure
- `20260403_181500_orbit_bundle_p4m6`
  - real-orbit bundle template projection
  - conclusion: physically interpretable but still too late-stage
- `20260403_183500_bundle_phase_demod_p4m6`
  - phase-aware bundle demodulation
  - conclusion: slightly more structured than direct projection, still not competitive

### 14.5 Orbit-aware SH families

- `20260403_191500_sh_orbit_bundle`
  - orbit-order-weighted SH prototypes
  - conclusion: orbit-derived order weighting was insufficient
- `20260403_193200_sh_orbit_carrier`
  - carrier-removed orbit-aware SH demodulation
  - conclusion: still failed badly on severe months

### 14.6 Pseudo-moire proxy families

- `20260403_200200_pseudo_moire`
  - pseudo-moire operator on final maps
  - conclusion: collapsed numerically to the same class as bundle-template projection
- `20260403_201200_sampling_operator`
  - richer sampling-operator proxy
  - conclusion: no additional identifiable information at final-map stage

### 14.7 First inversion-side prototype

- `20260404_101500_sampling_inversion`
  - first sampling-aware inversion-side SH residual prototype
  - conclusion: moving earlier in the pipeline is directionally right, but this first version was still only a smoothing regularizer

### 14.8 How to use this timeline

This timeline can be used in two ways:

- as an engineering audit trail for reproducing the experiment chain;
- as a research appendix showing that the negative results were systematic and progressively informed by theory, rather than arbitrary trial and error.

## 15. Files and Result Paths

### 13.1 Main implementation files

- [hsaf.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/filters/hsaf.py)
- [hsaf_sh.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/filters/hsaf_sh.py)
- [hsaf_experiments.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/app/hsaf_experiments.py)
- [sampling_aware.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/inversion/sampling_aware.py)
- [grace_l1b_fetch.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/app/grace_l1b_fetch.py)
- [grace_groundtrack.py](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/app/grace_groundtrack.py)

### 13.2 Main test files

- [test_hsaf_experimental.py](/G:/GRACE_Level2_pipeline_exc/python/tests/test_hsaf_experimental.py)
- [test_grace_l1b_fetch.py](/G:/GRACE_Level2_pipeline_exc/python/tests/test_grace_l1b_fetch.py)
- [test_grace_groundtrack.py](/G:/GRACE_Level2_pipeline_exc/python/tests/test_grace_groundtrack.py)
- [test_sampling_aware.py](/G:/GRACE_Level2_pipeline_exc/python/tests/test_sampling_aware.py)

### 13.3 Main result folders

- [20260402_224207](/G:/GRACE_Level2_pipeline_exc/output/local/compare/hsaf_experiments/20260402_224207)
- [20260403_125220](/G:/GRACE_Level2_pipeline_exc/output/local/compare/hsaf_experiments/20260403_125220)
- [20260403_133618](/G:/GRACE_Level2_pipeline_exc/output/local/compare/hsaf_experiments/20260403_133618)
- [20260403_155200_p4m6_sh](/G:/GRACE_Level2_pipeline_exc/output/local/compare/hsaf_experiments/20260403_155200_p4m6_sh)
- [20260403_181500_orbit_bundle_p4m6](/G:/GRACE_Level2_pipeline_exc/output/local/compare/hsaf_experiments/20260403_181500_orbit_bundle_p4m6)
- [20260403_183500_bundle_phase_demod_p4m6](/G:/GRACE_Level2_pipeline_exc/output/local/compare/hsaf_experiments/20260403_183500_bundle_phase_demod_p4m6)
- [20260403_191500_sh_orbit_bundle](/G:/GRACE_Level2_pipeline_exc/output/local/compare/hsaf_experiments/20260403_191500_sh_orbit_bundle)
- [20260403_193200_sh_orbit_carrier](/G:/GRACE_Level2_pipeline_exc/output/local/compare/hsaf_experiments/20260403_193200_sh_orbit_carrier)
- [20260403_200200_pseudo_moire](/G:/GRACE_Level2_pipeline_exc/output/local/compare/hsaf_experiments/20260403_200200_pseudo_moire)
- [20260403_201200_sampling_operator](/G:/GRACE_Level2_pipeline_exc/output/local/compare/hsaf_experiments/20260403_201200_sampling_operator)
- [20260404_101500_sampling_inversion](/G:/GRACE_Level2_pipeline_exc/output/local/compare/hsaf_experiments/20260404_101500_sampling_inversion)

## 16. Bottom-Line Conclusion

The current evidence does not support any of the tested HSA-based post-filter or weak inversion-side variants as a replacement for the present baseline HSAF, let alone DDK4.

The strongest conclusion from this phase is:

- HSA is not useless for GRACE;
- but HSA must be embedded inside a physically grounded sampling-aware stripe model;
- without that step, most elegant-looking HSA variants remain heuristic and systematically underperform.

## 17. Rendering Note

This Markdown file intentionally uses plain-text formulas and fenced code blocks instead of LaTeX block math, because the current Markdown preview used in this project does not render LaTeX expressions correctly.  
This is why the equations are written in directly readable text form rather than relying on a math extension.
