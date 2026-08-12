# 批量语法检查
import ast
for fn in ['decision_card.py', 'predict_engine_v3.py', 'predict_engine_v4.py', 'calibrate.py', 'db.py', 'webui.py']:
    try:
        ast.parse(open(fn, encoding='utf-8').read())
        print(f'✅ {fn}')
    except SyntaxError as e:
        print(f'❌ {fn}: {e}')
