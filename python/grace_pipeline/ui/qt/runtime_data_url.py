"""Official data landing pages."""

def data_url(center, product):
    center = str(center or "").upper(); product = str(product or "GSM").upper()
    if product == "MASCON_NC" or center in {"CSR", "JPL", "GFZ", "GSFC"}:
        return "https://podaac.jpl.nasa.gov/GRACE"
    if center in {"HUST", "ITSG"}:
        return "https://icgem.gfz.de/tom_longtime"
    return "https://search.earthdata.nasa.gov/search"
