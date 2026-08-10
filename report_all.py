"""批量研报：自选股全部生成深度研报——保存 reports/ 目录"""
import os
os.environ['TQDM_DISABLE'] = '1'
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, 'C:/Users/23643/src_workflow/stock_predict')
from decision_card import get_watchlist
from report_deep import deep_report

def main():
    watch = get_watchlist()
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')
    os.makedirs(out_dir, exist_ok=True)
    print(f'📝 批量研报：{len(watch)} 只自选')
    for code, name in watch:
        try:
            report = deep_report(code, name)
            fn = os.path.join(out_dir, f'{code}_{name}.md')
            with open(fn, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f'✅ {name}（{code}）→ {fn}')
        except Exception as e:
            print(f'❌ {name}: {str(e)[:50]}')
    print(f'\n📂 研报已保存: {out_dir}')

if __name__ == '__main__':
    main()
