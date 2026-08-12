# 批量替换硬编码路径 -> paths.model_path()
import os, re

project = r'C:\Users\23643\src_workflow\stock_predict'
files = ['decision_card.py', 'predict_engine_v3.py', 'predict_engine_v4.py', 'price_alert.py',
         'stock_alert.py', 'calibrate.py', 'report_daily.py', 'report_all.py', 'data_health.py',
         'decision_archive.py', 'sentiment_llm.py', 'policy_tracker.py', 'news_analyze.py']

for fn in files:
    p = os.path.join(project, fn)
    if not os.path.exists(p):
        continue
    src = open(p, encoding='utf-8').read()
    orig = src
    # 模型路径: C:/Users/23643/src_workflow/stock_predict/model_x.joblib -> model_path('model_x.joblib')
    src = re.sub(r"C:/Users/23643/src_workflow/stock_predict/(model_[a-z0-9_]+\.joblib)",
                 r"model_path('\1')", src)
    src = re.sub(r"C:/Users/23643/src_workflow/stock_predict/(calibrator_[a-z0-9_]+\.joblib)",
                 r"model_path('\1')", src)
    if src != orig:
        # 确保 import paths（如果文件里用了 model_path 但没 import）
        if "model_path(" in src and "from paths import" not in src and "import paths" not in src:
            # 在第一个 import 后加
            lines = src.split('\n')
            inserted = False
            for i, ln in enumerate(lines[:8]):
                if ln.startswith('import ') or ln.startswith('from '):
                    lines.insert(i + 1, 'from paths import model_path')
                    inserted = True
                    break
            if not inserted:
                lines.insert(0, 'from paths import model_path\n')
            src = '\n'.join(lines)
        open(p, 'w', encoding='utf-8').write(src)
        print(f'✅ {fn}')
    else:
        print(f'— {fn}（无改动）')
print('批量替换完成')
