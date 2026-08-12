# 修复嵌套引号：'model_path('x')' -> model_path('x')
import re

for fn in ['decision_card.py', 'predict_engine_v3.py', 'predict_engine_v4.py', 'calibrate.py']:
    src = open(fn, encoding='utf-8').read()
    orig = src
    # 'model_path('model_x.joblib')' -> model_path('model_x.joblib')
    src = re.sub(r"'(model_path\('[^']+'\))'", r"\1", src)
    # 也处理 "model_path(...)" 双引号
    src = re.sub(r"\"(model_path\('[^']+'\))\"", r"\1", src)
    if src != orig:
        open(fn, 'w', encoding='utf-8').write(src)
        print(f'✅ 修复 {fn}')
    else:
        print(f'— {fn}')

# 验证
import ast
for fn in ['decision_card.py', 'predict_engine_v3.py', 'predict_engine_v4.py', 'calibrate.py']:
    try:
        ast.parse(open(fn, encoding='utf-8').read())
        print(f'✅ 语法 {fn}')
    except SyntaxError as e:
        print(f'❌ {fn}: {e}')
