# Local modifications to pip-installed libraries

- **`gazefollower/calibration/SVRCalibration.py`**  
  - Modified SVM loading to use `cv.ml.SVM_load()` instead of `create().load()` for compatibility with newer OpenCV versions.

- **`eyetrax/models/__init__.py`**  
  - Replaced filesystem-based module discovery (`Path.iterdir()`) with:
    ```python
    for _, mod_name, _ in pkgutil.iter_modules(__path__):
        import_module(f"{__name__}.{mod_name}")
    ```
  - This ensures model modules are correctly discovered in both standard Python and PyInstaller-frozen environments, fixing `FileNotFoundError` on bundled builds.
