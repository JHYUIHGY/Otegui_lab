# This script performs image segmentation and analysis on fluorescence microscopy images.
# It extracts metadata from filenames, loads images, segments spots, measures their properties,
# and stores the results in an SQLite database.
# The script assumes the images are in TIFF format and follow a specific naming convention.
import os
import re
import sqlite3
import numpy as np
import tifffile
from skimage import filters, measure, morphology, segmentation
from skimage.color import label2rgb
import matplotlib.pyplot as plt


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


def normalize_image(img):
    """Normalize an image to the range 0-255."""
    img = img.astype(np.float32)  # Convert to float for processing
    img = (img - img.min()) / (img.max() - img.min()) * 255  # Stretch contrast, original image was too dim (only 0-170)
    return img.astype(np.uint8)  # Convert back to uint8


def load_tif(fname):
    try:
        img = tifffile.imread(fname)
        if not isinstance(img, np.ndarray):
            raise ValueError(f"File {fname} could not be loaded as an image.")
        
        # print(f"Loaded {fname} with shape: {img.shape}, dtype: {img.dtype}")  

        # Convert RGB to grayscale
        if img.ndim == 3 and img.shape[2] == 3:
            print("Converting RGB image to grayscale.")
            img = np.mean(img, axis=2).astype(np.uint8)

        elif img.ndim > 2:  
            img = img[0, ...]  # Take the first slice if it's a stack

        img = normalize_image(img)
        # print(f"Final shape after processing: {img.shape}, unique values: {np.unique(img)}")
        
        return img

    except Exception as e:
        print(f"Error loading {fname}: {e}")
        return None  


def segment_and_measure_spots(image, min_area=5, closing_radius=3, opening_radius=1) -> tuple[list, np.ndarray]:
    """
    Segments bright 'spots' in a fluorescence image using simple thresholding
    and morphological cleanup. Returns a list of region measurements.
    
    Input image : 2D np.array

    Returns list of dict
        Each dict has { 'label': int, 'area': float, 'mean_intensity': float,
                        'integrated_intensity': float, etc. }
    """
    # Adaptive thresholding using Gaussian-weighted local mean
    thresh_val = filters.threshold_local(image, block_size=201, method='gaussian') # adjust block_size base on your need
    mask = image > thresh_val
    
    # Morphological refinement
    mask = morphology.binary_closing(mask, morphology.disk(closing_radius))
    mask = morphology.binary_opening(mask, morphology.disk(opening_radius))
    # Remove small artifacts and edge touching objects
    mask = morphology.remove_small_objects(mask, min_size=min_area)
    mask = segmentation.clear_border(mask)
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
                "integrated_intensity": p.mean_intensity * p.area,
            })
    return measurements, mask


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

def visualize_segmentation_detailed(image, mask, labeled_image=None, measurements=None, output_path=None):
    """
    Create a detailed visualization of segmentation results.
    
    Required:
    - image: Original 2D NumPy array (grayscale)
    - mask: Binary segmentation mask (same dimensions as 'image')
    """

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Determine how many subplots (2 if no labeled_image, otherwise 3)
    num_plots = 2 if labeled_image is None else 3
    fig, axes = plt.subplots(1, num_plots, figsize=(12, 5))
    
    # If only 2 subplots, axes will be a single numpy array of length 2
    # For consistency, handle that by turning 'axes' into a list
    if num_plots == 2:
        axes = list(axes)
    else:
        axes = list(axes)

    # Original image
    axes[0].imshow(image, cmap='gray')
    axes[0].set_title('Original Image')
    axes[0].axis('off')
    
    # Binary mask
    axes[1].imshow(mask, cmap='binary')
    axes[1].set_title('Segmentation Mask')
    axes[1].axis('off')
    
    # If we have a labeled image, show it
    if labeled_image is not None:
        overlay = label2rgb(labeled_image, image=image, bg_label=0)
        axes[2].imshow(overlay)
        axes[2].set_title('Labeled Segments')
        axes[2].axis('off')
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=200) # Change dpi on your need
        plt.close()
    else:
        plt.show()