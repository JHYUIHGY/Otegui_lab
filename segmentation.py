# This script performs image segmentation and analysis on fluorescence microscopy images.
# It extracts metadata from filenames, loads images, segments spots, measures their properties,
# and stores the results in an SQLite database.
# The script assumes the images are in TIFF format and follow a specific naming convention.
import os
import re
import sqlite3
import numpy as np
import tifffile
from skimage import filters, measure, morphology


def parse_filename(fname):
    """
    Extracts metadata such as magnification, seedling, z-slice, and channel
    from a filename of the form:
    '20X-something-something_seedlingN_something_overview_z0XcY.tif'
    
    Returns a dict of parsed fields.
    """
    #  (20X)-(anything up to 'seedling\d')-(anything)-z(\d+)c(\d+)
    pattern = (
        r"(?P<magnification>\d+X)-"          # e.g. "20X"
        r"(?P<rest>.*?)"                     # everything up to next dash or underscore
        r"_z(?P<zslice>\d+)c(?P<channel>\d+)" # e.g. "_z01c2"
        r"\.tif$"
    )
    match = re.search(pattern, fname)
    if not match:
        # If the pattern doesn't match, return something minimal
        return {
            "filename": fname,
            "magnification": None,
            "zslice": None,
            "channel": None
        }
    else:
        return {
            "filename": fname,
            "magnification": match.group("magnification"),
            "zslice": match.group("zslice"),
            "channel": match.group("channel")
        }


def load_tif(fname):
    """Load a single-channel TIFF image as a NumPy array."""
    img = tifffile.imread(fname)
    # For now, assume it's 2D or a single slice
    if img.ndim > 2:
        # if multidimension, pick the first dimension as needed
        img = img[0, ...]
    return img


def segment_and_measure_spots(image, min_area=5):
    """
    Segments bright 'spots' in a fluorescence image using simple thresholding
    and morphological cleanup. Returns a list of region measurements.
    
    Input image : 2D np.array

    Returns list of dict
        Each dict has { 'label': int, 'area': float, 'mean_intensity': float,
                        'integrated_intensity': float, etc. }
    """
    #Otsu's method to find threshold
    thresh_val = filters.threshold_otsu(image) 
    mask = image > thresh_val
    #Morphological cleanup to remove small objects
    mask = morphology.remove_small_objects(mask, min_size=min_area)
    #Label connected components
    labeled = measure.label(mask)
    #Measure properties including intensity
    props = measure.regionprops(labeled, intensity_image=image)
    
    measurements = []
    for p in props: #props is a regionprops object
        measurements.append({
            "label": p.label,
            "area_pixels": p.area,
            "mean_intensity": p.mean_intensity,
            "integrated_intensity": p.mean_intensity * p.area #total intensity
        })
    return measurements


def store_measurements_in_sql(db_path, metadata, measurements):
    """
    Stores spot measurements in an SQLite DB. 
    'metadata' is a dict with {filename, magnification, zslice, channel}.
    'measurements' is the list of measurement dicts from 'segment_and_measure_spots'.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS spots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        magnification TEXT,
        zslice TEXT,
        channel TEXT,
        label INTEGER,
        area_pixels REAL,
        mean_intensity REAL,
        integrated_intensity REAL
    )
    """)

    for m in measurements: 
        c.execute("""
            INSERT INTO spots (
                filename, magnification, zslice, channel,
                label, area_pixels, mean_intensity, integrated_intensity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metadata.get("filename"),
            metadata.get("magnification"),
            metadata.get("zslice"), 
            metadata.get("channel"),
            m["label"],
            m["area_pixels"],
            m["mean_intensity"],
            m["integrated_intensity"]
        ))

    conn.commit()
    conn.close()
