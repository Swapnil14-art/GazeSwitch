# Local modifications to pip-installed libraries

- `gazefollower/calibration/SVRCalibration.py`
  - Modified SVM loading to use `cv.ml.SVM_load()` instead of `create().load()`
