import os
import re
import ast
import sys
import json
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime


class SecurityAuditor:
    def __init__(self):
        self.patterns = {
            'sql_concat': [
                (r'\.execute\s*\(.*\+\s*[^)]+\)', 'Конкатенация строк в execute()'),
                (r'\.query\s*\(.*\+\s*[^)]+\)', 'Конкатенация строк в query()'),
                (r'f["\']SELECT.*["\']', 'f-строка с SQL запросом'),
                (r'text\s*\(.*%[^)]*\)', 'Форматирование строки в text()'),
                (r'\.filter\s*\(.*\+\s*[^)]+\)', 'Конкатенация в filter()'),
            ],
            'raw_sql': [
                (r'raw\s*\(.*\)', 'Использование raw SQL'),
                (r'from_statement', 'from_statement метод'),
                (r'session\.execute\s*\(["\']', 'session.execute с сырой строкой'),
            ],
            'dangerous_functions': [
                (r'eval\s*\(', 'Использование eval()'),
                (r'exec\s*\(', 'Использование exec()'),
                (r'__import__\s*\(', 'Динамический импорт'),
                (r'pickle\.loads', 'Десериализация pickle'),
                (r'yaml\.load', 'Загрузка YAML без safe_load'),
                (r'os\.system', 'Вызов системных команд'),
                (r'subprocess\.Popen', 'Запуск подпроцессов'),
            ],
            'file_security': [
                (r'open\s*\(.*user.*\)', 'Открытие файлов с пользовательским вводом'),
                (r'shutil\..*\(.*user.*\)', 'Операции с файлами с пользовательским вводом'),
                (r'os\.remove\s*\(.*user.*\)', 'Удаление файлов с пользовательским вводом'),
            ]
        }

    def audit_file(self, file_path: str) -> List[Dict]:
        issues = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            for category, patterns in self.patterns.items():
                for pattern, description in patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        line_content = content.split('\n')[line_num - 1].strip()

                        issues.append({
                            'file': file_path,
                            'line': line_num,
                            'category': category,
                            'description': description,
                            'code': line_content[:200],
                            'severity': self._get_severity(category)
                        })

            ast_issues = self._ast_analysis(file_path, content)
            issues.extend(ast_issues)

        except Exception as e:
            issues.append({
                'file': file_path,
                'line': 0,
                'category': 'error',
                'description': f'Ошибка при анализе файла: {str(e)}',
                'code': '',
                'severity': 'low'
            })

        return issues

    def _ast_analysis(self, file_path: str, content: str) -> List[Dict]:
        issues = []

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if hasattr(node.func, 'attr') and node.func.attr == 'execute':
                        for arg in node.args:
                            if self._has_string_concat(arg):
                                line_num = node.lineno
                                line_content = content.split('\n')[line_num - 1].strip()

                                issues.append({
                                    'file': file_path,
                                    'line': line_num,
                                    'category': 'sql_concat',
                                    'description': 'AST: Конкатенация строк в execute()',
                                    'code': line_content[:200],
                                    'severity': 'high'
                                })

                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['eval', 'exec']:
                            line_num = node.lineno
                            line_content = content.split('\n')[line_num - 1].strip()

                            issues.append({
                                'file': file_path,
                                'line': line_num,
                                'category': 'dangerous_functions',
                                'description': f'AST: Использование {node.func.id}()',
                                'code': line_content[:200],
                                'severity': 'critical'
                            })

                if isinstance(node, ast.JoinedStr):
                    for value in node.values:
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            if any(sql_keyword in value.value.upper()
                                   for sql_keyword in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP']):
                                line_num = node.lineno
                                line_content = content.split('\n')[line_num - 1].strip()

                                issues.append({
                                    'file': file_path,
                                    'line': line_num,
                                    'category': 'sql_concat',
                                    'description': 'AST: SQL в f-строке',
                                    'code': line_content[:200],
                                    'severity': 'high'
                                })

        except SyntaxError:
            pass

        return issues

    def _has_string_concat(self, node) -> bool:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return True
        elif isinstance(node, ast.JoinedStr):
            return True
        elif hasattr(node, 'values'):
            for child in node.values:
                if self._has_string_concat(child):
                    return True
        return False

    def _get_severity(self, category: str) -> str:
        severities = {
            'sql_concat': 'high',
            'raw_sql': 'medium',
            'dangerous_functions': 'critical',
            'file_security': 'medium',
            'error': 'low'
        }
        return severities.get(category, 'low')

    def generate_report(self, issues: List[Dict], output_format: str = 'text') -> str:
        if output_format == 'json':
            return json.dumps({
                'timestamp': datetime.now().isoformat(),
                'total_issues': len(issues),
                'issues': issues,
                'summary': self._generate_summary(issues)
            }, indent=2, ensure_ascii=False)

        report = []
        report.append("=" * 80)
        report.append("ОТЧЕТ АУДИТА БЕЗОПАСНОСТИ")
        report.append(f"Время генерации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        report.append("")

        if not issues:
            report.append("✅ Уязвимостей не обнаружено!")
            return '\n'.join(report)

        files = {}
        for issue in issues:
            if issue['file'] not in files:
                files[issue['file']] = []
            files[issue['file']].append(issue)

        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}

        for file_path, file_issues in files.items():
            report.append(f"📁 Файл: {file_path}")
            report.append("-" * 80)

            file_issues.sort(key=lambda x: severity_order.get(x['severity'], 4))

            for issue in file_issues:
                severity_icon = {
                    'critical': '🔴',
                    'high': '🟠',
                    'medium': '🟡',
                    'low': '🟢'
                }.get(issue['severity'], '⚪')

                report.append(f"  {severity_icon} Строка {issue['line']}: {issue['description']}")
                report.append(f"     Уровень: {issue['severity'].upper()}")
                report.append(f"     Код: {issue['code']}")
                report.append("")

            report.append("")

        summary = self._generate_summary(issues)
        report.append("📊 СВОДКА:")
        report.append("-" * 80)
        report.append(f"Всего файлов проверено: {len(files)}")
        report.append(f"Всего проблем: {len(issues)}")
        report.append(f"  🔴 Критических: {summary.get('critical', 0)}")
        report.append(f"  🟠 Высоких: {summary.get('high', 0)}")
        report.append(f"  🟡 Средних: {summary.get('medium', 0)}")
        report.append(f"  🟢 Низких: {summary.get('low', 0)}")
        report.append("")
        report.append("💡 РЕКОМЕНДАЦИИ:")
        report.append("-" * 80)

        if summary.get('critical', 0) > 0:
            report.append("1. НЕМЕДЛЕННО исправьте критические уязвимости!")

        if summary.get('high', 0) > 0:
            report.append("2. Исправьте высокоприоритетные SQL инъекции в течение 24 часов")

        if summary.get('sql_concat', 0) > 0:
            report.append("3. Замените все конкатенации строк на параметризованные запросы")

        if summary.get('raw_sql', 0) > 0:
            report.append("4. Используйте ORM вместо сырых SQL запросов")

        report.append("5. Всегда используйте подготовленные выражения (prepared statements)")
        report.append("6. Регулярно запускайте этот аудит после изменений кода")

        report.append("")
        report.append("=" * 80)
        report.append("✅ Аудит завершен")
        report.append("=" * 80)

        return '\n'.join(report)

    def _generate_summary(self, issues: List[Dict]) -> Dict:
        summary = {
            'total': len(issues),
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'sql_concat': 0,
            'raw_sql': 0,
            'dangerous_functions': 0,
            'file_security': 0
        }

        for issue in issues:
            summary[issue['severity']] += 1
            summary[issue['category']] += 1

        return summary


def find_python_files(directory: str = '.') -> List[str]:
    python_files = []

    for root, dirs, files in os.walk(directory):
        ignore_dirs = ['__pycache__', '.git', '.venv', 'venv', 'env', 'node_modules']
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))

    return python_files


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Аудит безопасности Python кода')
    parser.add_argument('path', nargs='?', default='.', help='Путь к директории или файлу')
    parser.add_argument('--format', choices=['text', 'json'], default='text',
                        help='Формат вывода (text/json)')
    parser.add_argument('--output', help='Файл для сохранения отчета')
    parser.add_argument('--exclude', help='Регулярное выражение для исключения файлов')

    args = parser.parse_args()

    print("🔍 Запуск аудита безопасности...")
    print(f"Путь: {args.path}")
    print(f"Формат: {args.format}")
    print()

    if os.path.isfile(args.path):
        files = [args.path]
    else:
        files = find_python_files(args.path)

    if args.exclude:
        import re
        exclude_pattern = re.compile(args.exclude)
        files = [f for f in files if not exclude_pattern.search(f)]

    print(f"Найдено Python файлов: {len(files)}")

    auditor = SecurityAuditor()
    all_issues = []

    for file_path in files:
        issues = auditor.audit_file(file_path)
        all_issues.extend(issues)

    report = auditor.generate_report(all_issues, args.format)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ Отчет сохранен в: {args.output}")
    else:
        print(report)

    summary = auditor._generate_summary(all_issues)
    if summary.get('critical', 0) > 0 or summary.get('high', 0) > 5:
        sys.exit(1)


if __name__ == "__main__":
    main()