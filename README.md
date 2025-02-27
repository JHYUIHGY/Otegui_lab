# Otegui Lab - Confocal Image Auto-Segmentation

## Overview
This project focuses on automating the segmentation of confocal microscopy images for the Otegui Lab. It processes fluorescence microscopy images, extracts metadata, applies segmentation, and stores results in an SQLite database.

## Features
- **Automated Segmentation**: Uses adaptive thresholding and morphological operations to identify bright spots in fluorescence images.
- **Metadata Extraction**: Parses image filenames to extract relevant metadata (e.g., magnification, z-slice, and channel).
- **Database Storage**: Saves segmentation measurements into an SQLite database for further analysis.
- **Visualization**: Generates visual outputs showing the original image, segmentation mask, and labeled segments.

## Getting Started
### Prerequisites
Ensure you have the following dependencies installed:
```sh
pip install numpy tifffile scikit-image matplotlib sqlite3
```

### Running the Segmentation
Execute the script to process images:
```sh
python3 seg_process.py
```
This will:
1. Load `.tif` images from the `confocal_images/` folder.
2. Convert RGB images to grayscale (if applicable).
3. Apply segmentation to detect bright spots.
4. Save results in `results.db` and generate visualization images in the `results/` folder.

### Overwriting Results
Each time `seg_process.py` is run, it overwrites previous `.png` visualizations. To also overwrite the database, modify `store_measurements_in_sql()` in `segmentation.py` to clear existing data before inserting new records:
```python
c.execute("DELETE FROM spots")  # Clears old data before inserting new entries
```

## File Structure
```
Otegui_lab/
├── confocal_images/     # Input confocal microscopy images (.tif)
├── results/             # Processed segmentation outputs (.png)
├── results.db           # SQLite database storing measurements
├── seg_process.py       # Main script for running segmentation
├── segmentation.py      # Core segmentation and processing functions
├── segmentation.ipynb   # Jupyter notebook for testing segmentation
├── manual_load.ipynb    # Additional notebook for manual testing
└── .gitignore           # Ignoring unnecessary files
```

## Contributions
This repository can be pulled, but only the owner and authorized collaborators can push updates. If you have suggestions, feel free to reach out.

## Contact
For questions or access requests, please contact **Yuxin Duan** at yduan47@wisc.edu.

