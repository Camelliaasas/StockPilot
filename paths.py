"""统一路径：打包(exe) vs 开发 环境自适应"""
import sys, os

def project_root():
    """项目根目录（打包=资源目录 _MEIPASS / 开发=脚本目录）"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def model_path(name):
    """模型文件路径（打包后也在资源目录）"""
    return os.path.join(project_root(), name)

def data_path():
    """数据文件路径（data.db——打包后放用户目录——可写）"""
    if getattr(sys, 'frozen', False):
        d = os.path.join(os.path.expanduser('~'), 'StockPilotData')
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, 'data.db')
    return os.path.join(project_root(), 'data.db')
