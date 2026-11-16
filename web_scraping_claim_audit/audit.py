"""Offline, module-scoped syntax analysis; source is never executed."""
import ast
import os
import re
from pathlib import Path
from .phrases import WEBSCRAPING, NOWEBSCRAPING, GENERIC_NAMES


def normalize(text):
    return re.sub(r'\s+', ' ', text.lower().replace('’', "'").replace("n't", ' not').replace('-', ' ')).strip()


def matches(text, phrases):
    pattern = r'\b(?:' + '|'.join(re.escape(p) for p in sorted(phrases, key=lambda p: (-len(p), p))) + r')\b'
    return list(re.finditer(pattern, text))


def claims(text):
    lines = []
    fence = None
    for line in text.splitlines():
        m = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if m and m[1][0] == fence[0] and len(m[1]) >= len(fence) and not m[2].strip():
                fence = None
            lines.append('')
        elif m:
            fence = m[1]
            lines.append('')
        else:
            lines.append(line)
    yes, no = [], []
    for paragraph in re.split(r'\n\s*\n', '\n'.join(lines)):
        text = normalize(paragraph)
        denials = matches(text, NOWEBSCRAPING)
        no.extend(m[0] for m in denials)
        for m in reversed(denials):
            text = text[:m.start()] + ' ' + text[m.end():]
        yes.extend(m[0] for m in matches(text, WEBSCRAPING))
    return yes, no


def evidence(source):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return False
    nodes = list(ast.walk(tree))
    shadows = {n.name for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    bindings = {}
    for n in nodes:
        if isinstance(n, ast.Import):
            for a in n.names:
                bindings[a.asname or a.name.split('.')[0]] = a.name if a.asname else a.name.split('.')[0]
        elif isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                bindings[a.asname or a.name] = n.module + '.' + a.name

    def resolve(n):
        if isinstance(n, ast.Name):
            return bindings.get(n.id, '') if n.id not in shadows else ''
        if isinstance(n, ast.Attribute):
            base = resolve(n.value)
            return base + '.' + n.attr if base and n.attr not in shadows else ''
        if isinstance(n, ast.Call):
            return resolve(n.func)
        return ''

    # Iterate to support assignments that refer to earlier aliases or constructors.
    for _ in range(len(bindings) + len(nodes) + 1):
        previous = bindings.copy()
        for n in nodes:
            pairs = []
            if isinstance(n, ast.Assign):
                pairs = [(t, n.value) for t in n.targets]
            elif isinstance(n, ast.AnnAssign) and n.value:
                pairs = [(n.target, n.value)]
            elif isinstance(n, (ast.With, ast.AsyncWith)):
                pairs = [(i.optional_vars, i.context_expr) for i in n.items if i.optional_vars]
            for target, value in pairs:
                if isinstance(target, ast.Name) and target.id not in shadows:
                    value = resolve(value)
                    if value and bindings.get(target.id) != value:
                        bindings[target.id] = value
        if bindings == previous:
            break

    flags = set()
    for n in nodes:
        if isinstance(n, ast.ClassDef):
            if any(resolve(b) == 'scrapy.Spider' or (isinstance(b, ast.Attribute) and b.attr == 'Spider' and b.attr not in shadows and resolve(b.value).split('.')[0] == 'scrapy') for b in n.bases):
                flags.add('scrapy')
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        full = resolve(f)
        attr = f.attr if isinstance(f, ast.Attribute) and f.attr not in shadows else ''
        root = resolve(f.value) if isinstance(f, ast.Attribute) else ''
        if (isinstance(f, ast.Name) and full in {'requests.get', 'requests.request', 'httpx.get', 'urllib.request.urlopen'}) or (attr in {'get', 'request'} and root.split('.')[0] in {'requests', 'httpx'}) or (attr == 'urlopen' and root.startswith('urllib.request')):
            flags.add('fetch')
        if full == 'bs4.BeautifulSoup' or (attr == 'BeautifulSoup' and root.split('.')[0] == 'bs4'):
            flags.add('soup')
        if full in {'lxml.html.fromstring', 'lxml.etree.HTML'} or (attr == 'fromstring' and root.startswith('lxml.html')) or (attr == 'HTML' and root.startswith('lxml.etree')):
            flags.add('lxml')
        if full in {'scrapy.Request', 'scrapy.FormRequest', 'scrapy.http.Request', 'scrapy.http.FormRequest'} or (attr in {'Request', 'FormRequest'} and root.split('.')[0] == 'scrapy'):
            flags.add('scrapy')
        if attr:
            flags.add(attr)
        if (attr in GENERIC_NAMES) or (isinstance(f, ast.Name) and full and full.rsplit('.', 1)[-1] in GENERIC_NAMES and full.rsplit('.', 1)[-1] not in shadows):
            return True
    return bool(({'fetch', 'soup'} <= flags and flags & {'find', 'find_all', 'select'}) or ({'fetch', 'lxml', 'xpath'} <= flags) or ('scrapy' in flags and flags & {'css', 'xpath'}) or ('goto' in flags and flags & {'locator', 'query_selector', 'query_selector_all', 'inner_text', 'content'}) or ('get' in flags and flags & {'find_element', 'find_elements'}))


def audit(repo='.', ignore=()):
    root = Path(repo)
    if not root.is_dir() or not os.access(root, os.R_OK | os.X_OK):
        raise OSError('Repository must be a readable directory')
    positive, negative, production, tests = [], [], [], []
    def ignored(path):
        return any(path == p.rstrip('/') or path.startswith(p.rstrip('/') + '/') for p in ignore)
    def onerror(error):
        raise error
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
        dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink() and not ignored((Path(directory) / d).relative_to(root).as_posix()) and d not in {'.git', '.venv', 'venv', '__pycache__', 'build', 'dist'})
        for name in sorted(files):
            path = Path(directory) / name
            rel = path.relative_to(root)
            if path.is_symlink() or ignored(rel.as_posix()):
                continue
            if (rel.as_posix() == 'README.md' or ('docs' in rel.parts and path.suffix == '.md')):
                yes, no = claims(path.read_text(encoding='utf-8'))
                positive.extend({'path': rel.as_posix(), 'phrase': p} for p in yes)
                negative.extend({'path': rel.as_posix(), 'phrase': p} for p in no)
            if path.suffix == '.py' and not set(rel.parts[:-1]) & {'fixtures', 'docs', 'examples'}:
                if evidence(path.read_text(encoding='utf-8')):
                    is_test = 'tests' in rel.parts[:-1] or name.startswith('test_') or name.endswith('_test.py')
                    (tests if is_test else production).append(rel.as_posix())
    findings = []
    if positive and not production:
        findings.append({'id': 'documented-web-scraping-claim-false', 'severity': 'MEDIUM' if tests else 'HIGH', 'message': 'Evidence exists only in tests.' if tests else 'Documented capability has no production evidence.', 'claims': positive})
    if negative and production:
        findings.append({'id': 'documented-no-web-scraping-claim-false', 'severity': 'HIGH', 'message': 'Documented denial conflicts with production evidence.', 'claims': negative})
    return {'verdict': 'FAIL' if findings else 'PASS', 'findings': findings, 'evidence': production, 'test_evidence': tests}
