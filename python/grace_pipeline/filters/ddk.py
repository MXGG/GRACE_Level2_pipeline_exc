"""
DDK decorrelation filter for spherical harmonic coefficients.

The DDK filter uses precomputed decorrelation kernels based on
signal and error covariance. DDK1 = strongest, DDK8 = weakest.
"""

import re
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

import scipy.io as sio

from grace_pipeline.core.config import get_data_dir, get_root_dir


# DDK kernel cache
_ddk_cache: Dict[str, Any] = {}
_ddk_last_error: Dict[str, str] = {}

_DDK_BIN_MAP = {
    'DDK1': 'Wbd_2-120.a_1d14p_4',
    'DDK2': 'Wbd_2-120.a_1d13p_4',
    'DDK3': 'Wbd_2-120.a_1d12p_4',
    'DDK4': 'Wbd_2-120.a_5d11p_4',
    'DDK5': 'Wbd_2-120.a_1d11p_4',
    'DDK6': 'Wbd_2-120.a_5d10p_4',
    'DDK7': 'Wbd_2-120.a_1d10p_4',
    'DDK8': 'Wbd_2-120.a_5d9p_4',
}


def _read_bin_ddk(path: Path) -> Dict[str, Any]:
    """Read GRACE-filter-master binary DDK matrix."""
    with open(path, 'rb') as f:
        endian = np.fromfile(f, dtype='<u2', count=1)
        if endian.size == 0:
            raise ValueError('Empty DDK file')
        if endian[0] != 18754:
            f.seek(0)
            endian = np.fromfile(f, dtype='>u2', count=1)
            endian_char = '>'
        else:
            endian_char = '<'

        ver_bytes = f.read(6)
        ver_str = ('BI' + ver_bytes.decode('ascii', errors='ignore'))
        ver_str = ver_str.replace('\x00', '')
        m = re.search(r"\d+\.\d+", ver_str)
        ver = float(m.group(0)) if m else 0.0

        type_str = f.read(8).decode('ascii', errors='ignore')
        type_str = type_str.replace('\x00', '').strip()
        _ = f.read(80)  # descr

        meta = np.fromfile(f, dtype=endian_char + 'u4', count=4)
        if meta.size < 4:
            raise ValueError('Invalid DDK header')
        nints, ndbls, nval1, nval2 = [int(x) for x in meta]

        if ver < 2.4:
            pvals = np.fromfile(f, dtype=endian_char + 'u4', count=2)
        else:
            pvals = np.fromfile(f, dtype=endian_char + 'u8', count=2)
        if pvals.size < 2:
            raise ValueError('Invalid DDK header pval')
        pval1, pval2 = [int(x) for x in pvals]

        if ver <= 2.1:
            # Compatibility for old formats
            if type_str in ('SYMV0___', 'BDFULLV0', 'BDSYMV0', 'BDSYMV0_', 'BDFULLVN'):
                nvec = 0
                pval2 = 1
            elif type_str == 'SYMV1___':
                nvec = 1
                pval2 = 1
            elif type_str == 'SYMV2___':
                nvec = 2
                pval2 = 1
            elif type_str == 'FULLSQV0':
                nvec = 0
                pval2 = pval1
            else:
                nvec = 0
            nread = 0
            nval2 = nval1
        else:
            nvec = int(np.fromfile(f, dtype=endian_char + 'i4', count=1)[0])
            nread = int(np.fromfile(f, dtype=endian_char + 'i4', count=1)[0])

        nblocks = 0
        if type_str in ('BDSYMV0_', 'BDSYMV0', 'BDFULLV0', 'BDSYMVN_', 'BDFULLVN'):
            nblocks = int(np.fromfile(f, dtype=endian_char + 'i4', count=1)[0])

        # readme
        if nread > 0:
            f.read(nread * 80)

        ints_d = []
        ints = []
        if nints > 0:
            raw = f.read(nints * 24)
            ints_d = [raw[i*24:(i+1)*24].decode('ascii', errors='ignore').strip() for i in range(nints)]
            dtype_ints = endian_char + ('i4' if ver <= 2.4 else 'i8')
            ints = np.fromfile(f, dtype=dtype_ints, count=nints)

        if ndbls > 0:
            f.read(ndbls * 24)
            np.fromfile(f, dtype=endian_char + 'f8', count=ndbls)

        # side1_d
        f.read(nval1 * 24)

        blockind = None
        if type_str in ('BDSYMV0_', 'BDSYMV0', 'BDFULLV0', 'BDSYMVN_', 'BDFULLVN'):
            blockind = np.fromfile(f, dtype=endian_char + 'i4', count=nblocks)

        if type_str in ('BDFULLV0', 'BDFULLVN', 'FULLSQV0', 'FULLSQVN'):
            if ver > 2.2:
                f.read(nval2 * 24)
        elif type_str == 'FULL2DVN':
            f.read(nval2 * 24)

        if nvec > 0:
            np.fromfile(f, dtype=endian_char + 'f8', count=nval1 * nvec)

        pack1 = np.fromfile(f, dtype=endian_char + 'f8', count=pval1 * pval2)

    if blockind is None or pack1.size == 0:
        raise ValueError('Invalid DDK data: missing blockind/pack1')

    return {
        'type': type_str,
        'ver': ver,
        'nints': nints,
        'ints_d': ints_d,
        'ints': np.array(ints, dtype=int) if len(ints) else np.array([], dtype=int),
        'nblocks': int(nblocks),
        'blockind': np.array(blockind, dtype=int),
        'pack1': pack1,
    }


def _extract_lmin_lmax(kernel: Dict[str, Any], Lmax: int) -> Tuple[int, int]:
    nminfilt = 0
    nmaxfilt = Lmax
    for name, val in zip(kernel.get('ints_d', []), kernel.get('ints', [])):
        lname = name.strip().lower()
        if lname.startswith('lmax'):
            nmaxfilt = int(val)
        if lname.startswith('lmin'):
            nminfilt = int(val)
    return nminfilt, nmaxfilt


def _apply_ddk_block(C: np.ndarray, S: np.ndarray, Lmax: int, kernel: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    """Apply a binary DDK block kernel while preserving coefficients outside covered blocks."""
    nminfilt, nmaxfilt = _extract_lmin_lmax(kernel, Lmax)
    nmaxout = min(Lmax, nmaxfilt)

    C_f = np.array(C, copy=True)
    S_f = np.array(S, copy=True)

    lastblckind = 0
    lastindex = 0
    blockind = kernel['blockind']
    pack1 = kernel['pack1']
    nblocks = int(kernel['nblocks'])

    for iblk in range(1, nblocks + 1):
        order = iblk // 2
        if order > nmaxout:
            break
        trig = (iblk + (1 if iblk > 1 else 0)) % 2  # 1=cos, 0=sin
        sz = int(blockind[iblk - 1] - lastblckind)
        if sz <= 0:
            continue
        blockn = np.eye(nmaxfilt + 1 - order)
        nminblk = max(nminfilt, order)
        shft = nminblk - order
        block = pack1[lastindex:lastindex + sz * sz].reshape((sz, sz), order='F')
        blockn[shft:shft + sz, shft:shft + sz] = block

        sub = blockn[:nmaxout + 1 - order, :nmaxout + 1 - order]
        if trig == 1:
            C_f[order:nmaxout + 1, order] = sub @ C[order:nmaxout + 1, order]
        else:
            S_f[order:nmaxout + 1, order] = sub @ S[order:nmaxout + 1, order]

        lastblckind = int(blockind[iblk - 1])
        lastindex += sz * sz

    return C_f, S_f


def load_ddk_kernel(ddk_type: str, data_dir: str, Lmax: int = None) -> Optional[Any]:
    """
    Load DDK filter kernel matrix.

    Args:
        ddk_type: DDK filter type (e.g., 'DDK4')
        data_dir: Directory containing DDK kernel files or a specific file
        Lmax: Maximum degree (optional, used to select kernel size)

    Returns:
        DDK kernel matrix or kernel dict (binary) or None
    """
    global _ddk_cache, _ddk_last_error
    ddk_type = str(ddk_type).upper().strip()

    cache_key = f"{data_dir}/{ddk_type}/{Lmax or ''}"
    if cache_key in _ddk_cache:
        return _ddk_cache[cache_key]

    data_path = Path(data_dir)
    last_error = ""

    # Prefer binary kernels when available (GRACE-filter-master)
    if data_path.exists():
        bin_name = _DDK_BIN_MAP.get(ddk_type)
        if bin_name:
            bin_path = data_path / bin_name
            if bin_path.exists():
                try:
                    kernel = _read_bin_ddk(bin_path)
                    _ddk_cache[cache_key] = kernel
                    _ddk_last_error.pop(cache_key, None)
                    return kernel
                except Exception as exc:
                    last_error = f"failed to read binary kernel {bin_path}: {exc}"
    files = []
    if data_path.is_file():
        files = [data_path]
    elif data_path.exists():
        try:
            files = list(data_path.rglob('*.mat'))
        except Exception as exc:
            last_error = f"failed to scan {data_path}: {exc}"
            files = []

    # Common filename patterns
    patterns = [
        f"{ddk_type}.mat",
        f"{ddk_type.lower()}.mat",
        f"ddk{ddk_type[-1]}.mat",
        f"DDK{ddk_type[-1]}_filter.mat",
    ]
    for pattern in patterns:
        fp = data_path / pattern
        if fp.exists():
            files.insert(0, fp)

    # Prefer files containing DDK in name
    def _score_file(fp: Path) -> int:
        name = fp.name.lower()
        if ddk_type.lower() in name:
            return 0
        if f"ddk{ddk_type[-1]}" in name:
            return 1
        if "ddk" in name:
            return 2
        return 3

    files = sorted({str(f): f for f in files}.values(), key=_score_file)
    ncoeff = None
    if Lmax is not None:
        ncoeff = (Lmax + 1) ** 2

    def _select_kernel(mat: dict) -> Optional[np.ndarray]:
        candidates = []
        for key, arr in mat.items():
            if key.startswith('_'):
                continue
            if isinstance(arr, np.ndarray) and arr.ndim == 2 and arr.shape[0] == arr.shape[1]:
                candidates.append(arr)
        if not candidates:
            return None
        if ncoeff is not None:
            candidates.sort(key=lambda a: (abs(a.shape[0] - ncoeff), -a.shape[0]))
        else:
            candidates.sort(key=lambda a: -a.shape[0])
        return candidates[0]

    for fp in files:
        try:
            data = sio.loadmat(str(fp))
            kernel = _select_kernel(data)
            if kernel is not None:
                _ddk_cache[cache_key] = kernel
                _ddk_last_error.pop(cache_key, None)
                return kernel
        except Exception as exc:
            last_error = f"failed to read MAT kernel {fp}: {exc}"
            continue

    # Final fallback: try ROOT/data/DDK if a different path was provided
    try:
        root_ddk = get_data_dir(get_root_dir()) / "DDK"
        if root_ddk.exists() and root_ddk.resolve() != data_path.resolve():
            bin_name = _DDK_BIN_MAP.get(ddk_type)
            if bin_name:
                bin_path = root_ddk / bin_name
                if bin_path.exists():
                    kernel = _read_bin_ddk(bin_path)
                    _ddk_cache[cache_key] = kernel
                    _ddk_last_error.pop(cache_key, None)
                    return kernel
    except Exception as exc:
        last_error = f"failed fallback ROOT/data/DDK lookup: {exc}"

    if last_error:
        _ddk_last_error[cache_key] = last_error
    return None


def sh_to_vector(C: np.ndarray, S: np.ndarray, Lmax: int) -> np.ndarray:
    """
    Convert SH coefficient matrices to vector form.

    Ordering: [C00, C10, C11, S11, C20, C21, S21, C22, S22, ...]
    """
    n = (Lmax + 1) * (Lmax + 2)
    vec = np.zeros(n)

    idx = 0
    for l in range(Lmax + 1):
        for m in range(l + 1):
            vec[idx] = C[l, m]
            idx += 1
            if m > 0:
                vec[idx] = S[l, m]
                idx += 1

    return vec[:idx]


def vector_to_sh(vec: np.ndarray, Lmax: int) -> Tuple[np.ndarray, np.ndarray]:
    """Convert vector to SH coefficient matrices."""
    C = np.zeros((Lmax + 1, Lmax + 1))
    S = np.zeros((Lmax + 1, Lmax + 1))

    idx = 0
    for l in range(Lmax + 1):
        for m in range(l + 1):
            if idx < len(vec):
                C[l, m] = vec[idx]
                idx += 1
            if m > 0 and idx < len(vec):
                S[l, m] = vec[idx]
                idx += 1

    return C, S


def filter_sh_ddk(
    C: np.ndarray,
    S: np.ndarray,
    Lmax: int,
    ddk_type: str = 'DDK4',
    data_dir: str = '',
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """Apply DDK decorrelation filter to SH coefficients."""
    ddk_type = str(ddk_type).upper().strip()
    cache_key = f"{data_dir}/{ddk_type}/{Lmax or ''}"
    kernel = load_ddk_kernel(ddk_type, data_dir, Lmax)

    if kernel is None:
        meta = {
            'type': ddk_type,
            'applied': False,
            'error': 'DDK kernel not found',
        }
        if cache_key in _ddk_last_error:
            meta['detail'] = _ddk_last_error[cache_key]
        return C.copy(), S.copy(), meta

    is_3d = C.ndim == 3
    Nt = C.shape[2] if is_3d else 1

    C_f = np.array(C, copy=True)
    S_f = np.array(S, copy=True)

    for it in range(Nt):
        C_t = C[:, :, it] if is_3d else C
        S_t = S[:, :, it] if is_3d else S

        if isinstance(kernel, dict) and 'pack1' in kernel:
            C_out, S_out = _apply_ddk_block(C_t, S_t, Lmax, kernel)
        else:
            vec = sh_to_vector(C_t, S_t, Lmax)
            if len(vec) <= kernel.shape[0]:
                vec_f = vec.copy()
                vec_f[:len(vec)] = kernel[:len(vec), :len(vec)] @ vec
            else:
                n = kernel.shape[0]
                vec_f = vec.copy()
                vec_f[:n] = kernel @ vec[:n]
            C_out, S_out = vector_to_sh(vec_f, Lmax)

        if is_3d:
            C_f[:, :, it] = C_out
            S_f[:, :, it] = S_out
        else:
            C_f = C_out
            S_f = S_out

    meta = {
        'type': ddk_type,
        'applied': True,
    }

    return C_f, S_f, meta
