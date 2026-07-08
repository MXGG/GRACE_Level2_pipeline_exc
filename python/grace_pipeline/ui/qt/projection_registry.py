"""Projection registry and UI helpers for the preview page."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


PARAM_DEFS: dict[str, dict[str, Any]] = {
    "central_longitude": {
        "label": "Central longitude",
        "type": "float",
        "default": 0.0,
        "min": -180.0,
        "max": 180.0,
        "unit": "degree",
    },
    "central_latitude": {
        "label": "Central latitude",
        "type": "float",
        "default": 0.0,
        "min": -90.0,
        "max": 90.0,
        "unit": "degree",
    },
    "standard_parallels": {
        "label": "Standard parallels",
        "type": "float_pair",
        "default": [25.0, 45.0],
        "min": -90.0,
        "max": 90.0,
        "unit": "degree",
    },
    "true_scale_latitude": {
        "label": "True scale latitude",
        "type": "float",
        "default": 70.0,
        "min": -90.0,
        "max": 90.0,
        "unit": "degree",
    },
    "latitude_true_scale": {
        "label": "Latitude of true scale",
        "type": "float",
        "default": 0.0,
        "min": -80.0,
        "max": 80.0,
        "unit": "degree",
        "advanced": True,
    },
    "scale_factor": {
        "label": "Scale factor",
        "type": "float",
        "default": 0.9996,
        "min": 0.9,
        "max": 1.1,
        "advanced": True,
    },
    "false_easting": {"label": "False easting", "type": "float", "default": 0.0, "advanced": True},
    "false_northing": {"label": "False northing", "type": "float", "default": 0.0, "advanced": True},
    "zone": {"label": "UTM zone", "type": "int", "default": 49, "min": 1, "max": 60},
    "southern_hemisphere": {"label": "Southern hemisphere", "type": "bool", "default": False},
    "extent": {
        "label": "Extent",
        "type": "extent",
        "default": [-180.0, 180.0, -90.0, 90.0],
        "fields": ["lon_min", "lon_max", "lat_min", "lat_max"],
    },
    "azimuth": {
        "label": "Azimuth",
        "type": "float",
        "default": -60.0,
        "min": -180.0,
        "max": 180.0,
        "unit": "degree",
    },
    "elevation": {
        "label": "Elevation",
        "type": "float",
        "default": 25.0,
        "min": -90.0,
        "max": 90.0,
        "unit": "degree",
    },
    "roll": {
        "label": "Roll",
        "type": "float",
        "default": 0.0,
        "min": -180.0,
        "max": 180.0,
        "unit": "degree",
        "advanced": True,
    },
    "zoom": {"label": "Zoom", "type": "float", "default": 1.0, "min": 0.5, "max": 3.0},
    "projection_mode": {"label": "Projection", "type": "text", "default": "orthographic", "advanced": True},
    "focal_length": {"label": "Focal length", "type": "float", "default": 1.0, "min": 0.2, "max": 5.0, "advanced": True},
    "radius": {"label": "Radius", "type": "float", "default": 1.0, "min": 0.1, "max": 5.0, "internal": True},
    "surface_resolution": {"label": "Surface resolution", "type": "text", "default": "auto", "advanced": True},
    "relief_exaggeration": {
        "label": "Relief exaggeration",
        "type": "float",
        "default": 0.0,
        "min": 0.0,
        "max": 0.05,
        "advanced": True,
    },
    "vertical_exaggeration": {"label": "Vertical exaggeration", "type": "float", "default": 0.0, "advanced": True},
    "shading": {"label": "Shading", "type": "bool", "default": False, "advanced": True},
    "background_alpha": {"label": "Background alpha", "type": "float", "default": 1.0, "advanced": True},
}


PROJECTION_REGISTRY: dict[str, dict[str, Any]] = {
    "robinson": {
        "key": "robinson",
        "name": "Robinson",
        "group": "Global",
        "renderer": "cartopy",
        "crs_class": "Robinson",
        "crs_params": ["central_longitude"],
        "view_params": [],
        "advanced_params": [],
        "default": {"central_longitude": 0.0},
    },
    "mollweide": {
        "key": "mollweide",
        "name": "Mollweide",
        "group": "Global",
        "renderer": "cartopy",
        "crs_class": "Mollweide",
        "crs_params": ["central_longitude"],
        "view_params": [],
        "advanced_params": [],
        "default": {"central_longitude": 0.0},
    },
    "equal_earth": {
        "key": "equal_earth",
        "name": "Equal Earth",
        "group": "Global",
        "renderer": "cartopy",
        "crs_class": "EqualEarth",
        "crs_params": ["central_longitude"],
        "view_params": [],
        "advanced_params": [],
        "default": {"central_longitude": 0.0},
    },
    "winkel_tripel": {
        "key": "winkel_tripel",
        "name": "Winkel Tripel",
        "group": "Global",
        "renderer": "cartopy",
        "crs_class": "WinkelTripel",
        "crs_params": ["central_longitude"],
        "view_params": [],
        "advanced_params": [],
        "default": {"central_longitude": 0.0},
    },
    "eckert_iv": {
        "key": "eckert_iv",
        "name": "Eckert IV",
        "group": "Global",
        "renderer": "cartopy",
        "crs_class": "EckertIV",
        "crs_params": ["central_longitude"],
        "view_params": [],
        "advanced_params": [],
        "default": {"central_longitude": 0.0},
    },
    "sinusoidal": {
        "key": "sinusoidal",
        "name": "Sinusoidal",
        "group": "Global",
        "renderer": "cartopy",
        "crs_class": "Sinusoidal",
        "crs_params": ["central_longitude"],
        "view_params": [],
        "advanced_params": [],
        "default": {"central_longitude": 0.0},
    },
    "interrupted_goode_homolosine": {
        "key": "interrupted_goode_homolosine",
        "name": "Interrupted Goode Homolosine",
        "group": "Global",
        "renderer": "cartopy",
        "crs_class": "InterruptedGoodeHomolosine",
        "crs_params": ["central_longitude"],
        "view_params": [],
        "advanced_params": [],
        "default": {"central_longitude": 0.0},
    },
    "plate_carree": {
        "key": "plate_carree",
        "name": "Plate Carrée",
        "group": "Cylindrical",
        "renderer": "cartopy",
        "crs_class": "PlateCarree",
        "crs_params": ["central_longitude"],
        "view_params": ["extent"],
        "advanced_params": [],
        "default": {"central_longitude": 0.0, "extent": [-180.0, 180.0, -90.0, 90.0]},
    },
    "mercator": {
        "key": "mercator",
        "name": "Mercator",
        "group": "Cylindrical",
        "renderer": "cartopy",
        "crs_class": "Mercator",
        "crs_params": ["central_longitude"],
        "view_params": ["extent"],
        "advanced_params": ["latitude_true_scale", "false_easting", "false_northing"],
        "default": {"central_longitude": 0.0, "extent": [-180.0, 180.0, -80.0, 80.0]},
        "notes": "Do not use ±90° latitude extent for Mercator.",
    },
    "miller": {
        "key": "miller",
        "name": "Miller",
        "group": "Cylindrical",
        "renderer": "cartopy",
        "crs_class": "Miller",
        "crs_params": ["central_longitude"],
        "view_params": ["extent"],
        "advanced_params": [],
        "default": {"central_longitude": 0.0, "extent": [-180.0, 180.0, -85.0, 85.0]},
    },
    "lambert_cylindrical": {
        "key": "lambert_cylindrical",
        "name": "Lambert Cylindrical",
        "group": "Cylindrical",
        "renderer": "cartopy",
        "crs_class": "LambertCylindrical",
        "crs_params": ["central_longitude"],
        "view_params": ["extent"],
        "advanced_params": [],
        "default": {"central_longitude": 0.0, "extent": [-180.0, 180.0, -90.0, 90.0]},
    },
    "orthographic": {
        "key": "orthographic",
        "name": "Orthographic",
        "group": "Azimuthal",
        "renderer": "cartopy",
        "crs_class": "Orthographic",
        "crs_params": ["central_longitude", "central_latitude"],
        "view_params": [],
        "advanced_params": [],
        "default": {"central_longitude": 0.0, "central_latitude": 0.0},
    },
    "azimuthal_equidistant": {
        "key": "azimuthal_equidistant",
        "name": "Azimuthal Equidistant",
        "group": "Azimuthal",
        "renderer": "cartopy",
        "crs_class": "AzimuthalEquidistant",
        "crs_params": ["central_longitude", "central_latitude"],
        "view_params": ["extent"],
        "advanced_params": [],
        "default": {"central_longitude": 0.0, "central_latitude": 0.0, "extent": [-180.0, 180.0, -90.0, 90.0]},
    },
    "lambert_azimuthal_equal_area": {
        "key": "lambert_azimuthal_equal_area",
        "name": "Lambert Azimuthal Equal Area",
        "group": "Azimuthal",
        "renderer": "cartopy",
        "crs_class": "LambertAzimuthalEqualArea",
        "crs_params": ["central_longitude", "central_latitude"],
        "view_params": ["extent"],
        "advanced_params": [],
        "default": {"central_longitude": 0.0, "central_latitude": 0.0, "extent": [-180.0, 180.0, -90.0, 90.0]},
    },
    "stereographic": {
        "key": "stereographic",
        "name": "Stereographic",
        "group": "Azimuthal",
        "renderer": "cartopy",
        "crs_class": "Stereographic",
        "crs_params": ["central_longitude", "central_latitude"],
        "view_params": ["extent"],
        "advanced_params": ["true_scale_latitude", "false_easting", "false_northing"],
        "default": {"central_longitude": 0.0, "central_latitude": 90.0, "true_scale_latitude": 70.0, "extent": [-180.0, 180.0, 60.0, 90.0]},
    },
    "gnomonic": {
        "key": "gnomonic",
        "name": "Gnomonic",
        "group": "Azimuthal",
        "renderer": "cartopy",
        "crs_class": "Gnomonic",
        "crs_params": ["central_longitude", "central_latitude"],
        "view_params": ["extent"],
        "advanced_params": [],
        "default": {"central_longitude": 0.0, "central_latitude": 0.0, "extent": [-90.0, 90.0, -60.0, 60.0]},
    },
    "nearside_perspective": {
        "key": "nearside_perspective",
        "name": "Nearside Perspective",
        "group": "Azimuthal",
        "renderer": "cartopy",
        "crs_class": "NearsidePerspective",
        "crs_params": ["central_longitude", "central_latitude"],
        "view_params": [],
        "advanced_params": ["false_easting", "false_northing"],
        "default": {"central_longitude": 0.0, "central_latitude": 0.0},
    },
    "north_polar_stereographic": {
        "key": "north_polar_stereographic",
        "name": "North Polar Stereographic",
        "group": "Polar",
        "renderer": "cartopy",
        "crs_class": "NorthPolarStereo",
        "crs_params": ["central_longitude"],
        "view_params": ["extent"],
        "advanced_params": [],
        "default": {"central_longitude": 0.0, "extent": [-180.0, 180.0, 60.0, 90.0]},
    },
    "south_polar_stereographic": {
        "key": "south_polar_stereographic",
        "name": "South Polar Stereographic",
        "group": "Polar",
        "renderer": "cartopy",
        "crs_class": "SouthPolarStereo",
        "crs_params": ["central_longitude"],
        "view_params": ["extent"],
        "advanced_params": [],
        "default": {"central_longitude": 0.0, "extent": [-180.0, 180.0, -90.0, -60.0]},
    },
    "lambert_conformal": {
        "key": "lambert_conformal",
        "name": "Lambert Conformal",
        "group": "Conic",
        "renderer": "cartopy",
        "crs_class": "LambertConformal",
        "crs_params": ["central_longitude", "central_latitude", "standard_parallels"],
        "view_params": ["extent"],
        "advanced_params": ["false_easting", "false_northing"],
        "default": {"central_longitude": 105.0, "central_latitude": 35.0, "standard_parallels": [25.0, 45.0], "extent": [70.0, 140.0, 15.0, 55.0]},
    },
    "albers_equal_area": {
        "key": "albers_equal_area",
        "name": "Albers Equal Area",
        "group": "Conic",
        "renderer": "cartopy",
        "crs_class": "AlbersEqualArea",
        "crs_params": ["central_longitude", "central_latitude", "standard_parallels"],
        "view_params": ["extent"],
        "advanced_params": ["false_easting", "false_northing"],
        "default": {"central_longitude": 105.0, "central_latitude": 35.0, "standard_parallels": [25.0, 45.0], "extent": [70.0, 140.0, 15.0, 55.0]},
    },
    "transverse_mercator": {
        "key": "transverse_mercator",
        "name": "Transverse Mercator",
        "group": "Transverse",
        "renderer": "cartopy",
        "crs_class": "TransverseMercator",
        "crs_params": ["central_longitude", "central_latitude"],
        "view_params": ["extent"],
        "advanced_params": ["scale_factor", "false_easting", "false_northing"],
        "default": {"central_longitude": 105.0, "central_latitude": 0.0, "scale_factor": 0.9996, "extent": [100.0, 110.0, 25.0, 35.0]},
    },
    "utm": {
        "key": "utm",
        "name": "UTM",
        "group": "Transverse",
        "renderer": "cartopy",
        "crs_class": "UTM",
        "crs_params": ["zone", "southern_hemisphere"],
        "view_params": ["extent"],
        "advanced_params": [],
        "default": {"zone": 49, "southern_hemisphere": False, "extent": [108.0, 114.0, 27.0, 33.0]},
    },
    "globe_3d": {
        "key": "globe_3d",
        "name": "3D Globe",
        "group": "3D",
        "renderer": "matplotlib_3d",
        "crs_class": None,
        "crs_params": [],
        "view_params": ["central_longitude", "central_latitude", "azimuth", "elevation", "zoom"],
        "advanced_params": ["roll", "projection_mode", "focal_length", "relief_exaggeration", "surface_resolution", "shading", "background_alpha"],
        "default": {
            "central_longitude": 0.0,
            "central_latitude": 20.0,
            "azimuth": -60.0,
            "elevation": 25.0,
            "roll": 0.0,
            "zoom": 1.0,
            "projection_mode": "orthographic",
            "focal_length": 1.0,
            "radius": 1.0,
            "surface_resolution": "auto",
            "relief_exaggeration": 0.0,
            "shading": False,
            "background_alpha": 1.0,
        },
    },
}


PROJECTION_DISPLAY_NAMES = [spec["name"] for spec in PROJECTION_REGISTRY.values()]

_SCOPE_DEFAULTS: dict[str, dict[str, Any]] = {
    "global": {
        "recommended_scope": "global",
        "supports_global_extent": True,
        "default_extent": [-180.0, 180.0, -90.0, 90.0],
    },
    "world_without_poles": {
        "recommended_scope": "global",
        "supports_global_extent": True,
        "default_extent": [-180.0, 180.0, -80.0, 80.0],
    },
    "hemisphere": {
        "recommended_scope": "hemisphere",
        "supports_global_extent": False,
        "default_extent": [-90.0, 90.0, -60.0, 60.0],
    },
    "regional": {
        "recommended_scope": "regional",
        "supports_global_extent": False,
        "default_extent": [70.0, 140.0, 15.0, 55.0],
    },
    "small_region": {
        "recommended_scope": "regional",
        "supports_global_extent": False,
        "default_extent": [-60.0, 60.0, -45.0, 45.0],
    },
    "north_polar": {
        "recommended_scope": "polar",
        "supports_global_extent": False,
        "default_extent": [-180.0, 180.0, 50.0, 90.0],
    },
    "south_polar": {
        "recommended_scope": "polar",
        "supports_global_extent": False,
        "default_extent": [-180.0, 180.0, -90.0, -50.0],
    },
    "transverse": {
        "recommended_scope": "regional",
        "supports_global_extent": False,
        "default_extent": [100.0, 110.0, 25.0, 35.0],
    },
    "utm": {
        "recommended_scope": "regional",
        "supports_global_extent": False,
        "default_extent": [108.0, 114.0, 27.0, 33.0],
    },
    "3d": {
        "recommended_scope": "3d",
        "supports_global_extent": True,
        "default_extent": [-180.0, 180.0, -90.0, 90.0],
    },
}

_PROJECTION_SCOPES = {
    "robinson": "global",
    "mollweide": "global",
    "equal_earth": "global",
    "winkel_tripel": "global",
    "eckert_iv": "global",
    "sinusoidal": "global",
    "interrupted_goode_homolosine": "global",
    "plate_carree": "global",
    "mercator": "world_without_poles",
    "miller": "world_without_poles",
    "lambert_cylindrical": "global",
    "orthographic": "hemisphere",
    "azimuthal_equidistant": "hemisphere",
    "lambert_azimuthal_equal_area": "hemisphere",
    "stereographic": "north_polar",
    "gnomonic": "small_region",
    "nearside_perspective": "hemisphere",
    "north_polar_stereographic": "north_polar",
    "south_polar_stereographic": "south_polar",
    "lambert_conformal": "regional",
    "albers_equal_area": "regional",
    "transverse_mercator": "transverse",
    "utm": "utm",
    "globe_3d": "3d",
}

for _key, _spec in PROJECTION_REGISTRY.items():
    _scope = _PROJECTION_SCOPES.get(_key, "global")
    _scope_defaults = _SCOPE_DEFAULTS[_scope]
    _spec.setdefault("recommended_scope", _scope_defaults["recommended_scope"])
    _spec.setdefault("supports_global_extent", _scope_defaults["supports_global_extent"])
    _spec.setdefault("default_extent", deepcopy(_scope_defaults["default_extent"]))
    if "extent" in _spec.get("default", {}) and _key not in {"mercator", "miller"}:
        _spec["default_extent"] = deepcopy(_spec["default"]["extent"])
    if _key == "mercator":
        _spec["default_extent"] = [-180.0, 180.0, -80.0, 80.0]
    elif _key == "miller":
        _spec["default_extent"] = [-180.0, 180.0, -85.0, 85.0]
    elif _key == "north_polar_stereographic":
        _spec["default_extent"] = [-180.0, 180.0, 50.0, 90.0]
    elif _key == "south_polar_stereographic":
        _spec["default_extent"] = [-180.0, 180.0, -90.0, -50.0]

_LEGACY_LABELS = {
    "robinson (global)": "robinson",
    "robinson 全球折衷": "robinson",
    "plate carree": "plate_carree",
    "plate carrée": "plate_carree",
    "plate carrée 等经纬度": "plate_carree",
    "mollweide 全球等面积": "mollweide",
    "3d globe (surface)": "globe_3d",
    "3d globe": "globe_3d",
}

_CRS_ENGINE_NAMES = {
    "robinson": "Robinson",
    "mollweide": "Mollweide",
    "equal_earth": "EqualEarth",
    "winkel_tripel": "WinkelTripel",
    "eckert_iv": "EckertIV",
    "sinusoidal": "Sinusoidal",
    "interrupted_goode_homolosine": "InterruptedGoodeHomolosine",
    "plate_carree": "PlateCarree",
    "mercator": "Mercator",
    "miller": "Miller",
    "lambert_cylindrical": "LambertCylindrical",
    "orthographic": "Orthographic",
    "azimuthal_equidistant": "AzimuthalEquidistant",
    "lambert_azimuthal_equal_area": "LambertAzimuthalEqualArea",
    "stereographic": "Stereographic",
    "gnomonic": "Gnomonic",
    "nearside_perspective": "NearsidePerspective",
    "north_polar_stereographic": "NorthPolarStereo",
    "south_polar_stereographic": "SouthPolarStereo",
    "lambert_conformal": "LambertConformal",
    "albers_equal_area": "AlbersEqualArea",
    "transverse_mercator": "TransverseMercator",
    "utm": "UTM",
    "globe_3d": "globe_3d",
}


def projection_name_to_key(value: str | None) -> str:
    raw = (value or "").strip()
    if raw in PROJECTION_REGISTRY:
        return raw
    lower = raw.lower()
    if lower in _LEGACY_LABELS:
        return _LEGACY_LABELS[lower]
    for key, spec in PROJECTION_REGISTRY.items():
        if raw == spec["name"] or lower == str(spec["name"]).lower():
            return key
    compact = lower.replace(" ", "_").replace("-", "_")
    compact = compact.replace("é", "e")
    aliases = {
        "plate_carree": "plate_carree",
        "equalearth": "equal_earth",
        "winkeltripel": "winkel_tripel",
        "eckertiv": "eckert_iv",
        "azimuthalequidistant": "azimuthal_equidistant",
        "lambertconformal": "lambert_conformal",
        "albersequalarea": "albers_equal_area",
    }
    return aliases.get(compact, "robinson")


def projection_key_to_name(value: str | None) -> str:
    key = projection_name_to_key(value)
    return str(PROJECTION_REGISTRY.get(key, PROJECTION_REGISTRY["robinson"])["name"])


def projection_spec(value: str | None) -> dict[str, Any]:
    return PROJECTION_REGISTRY[projection_name_to_key(value)]


def projection_engine_name(value: str | None) -> str:
    return _CRS_ENGINE_NAMES.get(projection_name_to_key(value), "Robinson")


def projection_renderer(value: str | None) -> str:
    return str(projection_spec(value).get("renderer") or "cartopy")


def visible_projection_params(value: str | None, *, include_advanced: bool = False) -> list[str]:
    spec = projection_spec(value)
    params = list(spec.get("crs_params", [])) + list(spec.get("view_params", []))
    if include_advanced:
        params.extend(spec.get("advanced_params", []))
    return params


def projection_defaults(value: str | None) -> dict[str, Any]:
    spec = projection_spec(value)
    defaults = {name: deepcopy(defn.get("default")) for name, defn in PARAM_DEFS.items()}
    defaults.update(deepcopy(spec.get("default", {})))
    return defaults


def projection_default_extent(value: str | None) -> list[float]:
    return list(deepcopy(projection_spec(value).get("default_extent", [-180.0, 180.0, -90.0, 90.0])))


def projection_supports_global_extent(value: str | None) -> bool:
    return bool(projection_spec(value).get("supports_global_extent", True))


def projection_recommended_scope(value: str | None) -> str:
    return str(projection_spec(value).get("recommended_scope", "global"))


def is_global_extent(extent: list[float] | tuple[float, float, float, float] | None) -> bool:
    if not extent or len(extent) != 4:
        return False
    lon_min, lon_max, lat_min, lat_max = [float(v) for v in extent]
    return abs(lon_max - lon_min) >= 350.0 and lat_min <= -85.0 and lat_max >= 85.0
