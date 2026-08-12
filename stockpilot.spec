# StockPilot PyInstaller 打包配置
# 用法: pyinstaller stockpilot.spec
# -*- mode: python ; coding: utf-8 -*-
import os

project = r'C:\Users\23643\src_workflow\stock_predict'

datas = [
    (os.path.join(project, 'index.html'), '.'),
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
]

a = Analysis(
    [os.path.join(project, 'webui.py')],
    pathex=[project],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'lightgbm', 'sklearn.isotonic', 'sklearn.metrics',
        'akshare', 'pandas', 'numpy', 'joblib', 'flask',
        'websocket', 'socks',
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
    [],
    exclude_binaries=True,
    name='StockPilot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 无控制台窗口（GUI 启动）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='StockPilot',
)
