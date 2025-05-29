# 测试样例字典
test_cases = {
        "缺少包错误": """
Traceback (most recent call last):
  File "example.py", line 10, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'
        """,
        
        "导入名称错误": """
Traceback (most recent call last):
  File "data_analysis.py", line 15, in <module>
    from tensorflow.keras import SequentialModel
ImportError: cannot import name 'SequentialModel' from 'tensorflow.keras' (/usr/local/lib/python3.8/site-packages/tensorflow/keras/__init__.py)
        """,
        
        "属性错误": """
Traceback (most recent call last):
  File "script.py", line 25, in <module>
    result = numpy.random.randn_special(5, 5)
AttributeError: module 'numpy.random' has no attribute 'randn_special'
        """,
        
        "版本冲突": """
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts.
tensorflow 2.4.0 requires numpy~=1.19.2, but you have numpy 1.20.3 which is incompatible.
        """,
        
        "包中的语法错误": """
Traceback (most recent call last):
  File "main.py", line 8, in <module>
    from custom_package import function
  File "/usr/local/lib/python3.8/site-packages/custom_package/__init__.py", line 12
    if value == True
                   ^
SyntaxError: invalid syntax
        """,
        
        "DLL加载错误": """
Traceback (most recent call last):
  File "image_process.py", line 3, in <module>
    import cv2
  File "/usr/local/lib/python3.8/site-packages/cv2/__init__.py", line 5, in <module>
    from .cv2 import *
ImportError: DLL load failed while importing cv2: 找不到指定的模块。
        """,
        
        "依赖错误": """
ERROR: tensorboard 2.4.0 requires markdown>=2.6.8, which is not installed.
        """,
        
        "权限错误": """
Traceback (most recent call last):
  File "app.py", line 7, in <module>
    from package_name import module
  File "/usr/local/lib/python3.8/site-packages/package_name/__init__.py", line 10, in <module>
    with open('/var/log/app.log', 'w') as f:
PermissionError: [Errno 13] Permission denied: '/var/log/app.log'
        """,
        
        "复杂的多个错误": """
Traceback (most recent call last):
  File "complex_app.py", line 5, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'

Traceback (most recent call last):
  File "another_module.py", line 8, in <module>
    from matplotlib import special_plot
ImportError: cannot import name 'special_plot' from 'matplotlib' (/usr/local/lib/python3.8/site-packages/matplotlib/__init__.py)

ERROR: tensorflow 2.4.0 requires numpy~=1.19.2, but you have numpy 1.20.3 which is incompatible.
        """,
        
        "嵌套的导入错误": """
Traceback (most recent call last):
  File "deep_learning.py", line 3, in <module>
    import tensorflow as tf
  File "/usr/local/lib/python3.8/site-packages/tensorflow/__init__.py", line 8, in <module>
    from tensorflow.python import pywrap_tensorflow
  File "/usr/local/lib/python3.8/site-packages/tensorflow/python/__init__.py", line 25, in <module>
    from tensorflow.python.eager import context
  File "/usr/local/lib/python3.8/site-packages/tensorflow/python/eager/context.py", line 31, in <module>
    from tensorflow.python.framework import device as pydev
  File "/usr/local/lib/python3.8/site-packages/tensorflow/python/framework/device.py", line 21, in <module>
    from tensorflow.python.client import pywrap_tf_session
  File "/usr/local/lib/python3.8/site-packages/tensorflow/python/client/pywrap_tf_session.py", line 28, in <module>
    _pywrap_tf_session = swig_import_helper()
  File "/usr/local/lib/python3.8/site-packages/tensorflow/python/client/pywrap_tf_session.py", line 24, in swig_import_helper
    _mod = imp.load_module('_pywrap_tf_session', fp, pathname, description)
ImportError: libcudart.so.11.0: cannot open shared object file: No such file or directory
        """,
        
        "pkg_resources错误": """
Traceback (most recent call last):
  File "web_app.py", line 10, in <module>
    import flask
  File "/usr/local/lib/python3.8/site-packages/flask/__init__.py", line 14, in <module>
    from jinja2 import escape
  File "/usr/local/lib/python3.8/site-packages/jinja2/__init__.py", line 12, in <module>
    from .environment import Environment
  File "/usr/local/lib/python3.8/site-packages/jinja2/environment.py", line 25, in <module>
    from .defaults import BLOCK_END_STRING
  File "/usr/local/lib/python3.8/site-packages/jinja2/defaults.py", line 3, in <module>
    from .filters import FILTERS as DEFAULT_FILTERS  # noqa: F401
  File "/usr/local/lib/python3.8/site-packages/jinja2/filters.py", line 13, in <module>
    from markupsafe import soft_unicode
ImportError: cannot import name 'soft_unicode' from 'markupsafe' (/usr/local/lib/python3.8/site-packages/markupsafe/__init__.py)
        """
    }