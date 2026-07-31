import ast
import pathlib

ROOT = pathlib.Path('app/question_bank_v2/crud')

for p in sorted(ROOT.glob('crud_*.py')):
    tree = ast.parse(p.read_text(encoding='utf-8'))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not ast.get_docstring(node):
            print(f'{p.name}:{node.lineno} CLASS {node.name} 缺 docstring')
        for m in node.body:
            if not isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = ast.get_docstring(m)
            if not doc:
                print(f'{p.name}:{m.lineno} {node.name}.{m.name} 缺 docstring')
                continue
            args = [a.arg for a in m.args.args + m.args.kwonlyargs if a.arg not in ('self', 'cls')]
            if args and ':param' not in doc and len(doc.splitlines()) == 1:
                print(f'{p.name}:{m.lineno} {node.name}.{m.name} 单行 docstring 但有 {len(args)} 个参数')
            missing = [a for a in args if f':param {a}:' not in doc]
            if ':param' in doc and missing:
                print(f'{p.name}:{m.lineno} {node.name}.{m.name} :param 缺 {missing}')
            if ':param' in doc and ':return:' not in doc and not isinstance(m.returns, ast.Constant):
                print(f'{p.name}:{m.lineno} {node.name}.{m.name} 缺 :return:')
            if m.returns is None:
                print(f'{p.name}:{m.lineno} {node.name}.{m.name} 缺返回类型注解')
