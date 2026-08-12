# StockPilot 单文件 exe 打包配置（--onefile——双击即用）
# 用法: pyinstaller stockpilot_onefile.spec --noconfirm
# -*- mode: python ; coding: utf-8 -*-
import os

project = r'C:\Users\23643\src_workflow\stock_predict'

# 收集 akshare 数据文件（calendar.json 等——打包必缺）
import akshare as _ak
_ak_dir = os.path.dirname(_ak.__file__)
_ak_data = []
for _root, _dirs, _files in os.walk(os.path.join(_ak_dir, 'file_fold')):
    for _f in _files:
        _rel = os.path.relpath(os.path.join(_root, _f), _ak_dir)
        _ak_data.append((os.path.join(_root, _f), os.path.join('akshare', os.path.dirname(_rel))))

datas = [
    (os.path.join(project, 'index.html'), '.'),
    (os.path.join(project, 'echarts.min.js'), '.'),
    (os.path.join(project, 'model_lgbm.joblib'), '.'),
    (os.path.join(project, 'model_lgbm_hs300.joblib'), '.'),
    (os.path.join(project, 'model_lgbm_hs300_v2.joblib'), '.'),
    (os.path.join(project, 'model_stock_binary_full.joblib'), '.'),
    (os.path.join(project, 'model_stock_binary.joblib'), '.'),
    (os.path.join(project, 'model_stock_10d.joblib'), '.'),
    (os.path.join(project, 'model_index_binary.joblib'), '.'),
    (os.path.join(project, 'model_index_3d.joblib'), '.'),
    (os.path.join(project, 'model_index_3d_multi.joblib'), '.'),
    (os.path.join(project, 'model_index_5d.joblib'), '.'),
    (os.path.join(project, 'model_index.joblib'), '.'),
    (os.path.join(project, 'calibrator_index.joblib'), '.'),
    (os.path.join(project, '.env.example'), '.'),
    (os.path.join(project, 'demo_data.db'), '.'),
] + _ak_data

a = Analysis(
    [os.path.join(project, 'webui.py')],
    pathex=[project],
    binaries=[(r'C:\Users\23643\AppData\Local\hermes\hermes-agent\venv\Lib\site-packages\py_mini_racer\mini_racer.dll', 'py_mini_racer'),
              (r'C:\Users\23643\AppData\Local\hermes\hermes-agent\venv\Lib\site-packages\py_mini_racer\icudtl.dat', 'py_mini_racer')],
    datas=datas,
    hiddenimports=[
        'lightgbm', 'sklearn.isotonic', 'sklearn.metrics',
        'akshare', 'pandas', 'numpy', 'joblib', 'flask',
        'websocket', 'socks', 'py_mini_racer',
        'lxml', 'lxml._elementpath', 'py_mini_racer.ctypes_py_mini_racer',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PyQt5', 'PySide2', 'IPython'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='StockPilot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 无控制台窗口（静默启动）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
