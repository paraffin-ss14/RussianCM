"""Local Fluent editor. Run python server.py --open; never binds beyond loopback."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
import webbrowser

try:
    from fluent.syntax import FluentParser, ast
    from entities import scan_entities, literal
except ImportError:
    raise SystemExit('Установите зависимости: python -m pip install -r Tools/localization/requirements.txt')

HERE = Path(__file__).resolve().parent
VARIABLE = re.compile(r'\$[A-Za-z][A-Za-z0-9_-]*')


class EditorError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def parse(text):
    # Robust's Fluent dialect permits compact comments and variables in named
    # arguments. Adapt only parser input, preserving source character offsets.
    normalized = re.sub(r'(?m)^(#+)([^ \r\n#])', lambda m: m[1] + ' ', text)
    normalized = re.sub(r'(:\s*)(\$[A-Za-z][A-Za-z0-9_-]*)',
                        lambda m: m[1] + '0' + ' ' * (len(m[2]) - 1), normalized)
    return FluentParser(with_spans=True).parse(normalized)


def key_of(node):
    return ('-' if isinstance(node, ast.Term) else '') + node.id.name


def digest(data):
    return hashlib.sha256(data).hexdigest()


def entry_text(text, node):
    # Attached comments are outside the editable range and remain untouched.
    return text[node.id.span.start:node.span.end]


def pattern_text(text, node):
    parts = [text[node.value.span.start:node.value.span.end].strip()] if node.value else []
    parts.extend(a.id.name + '=' + text[a.value.span.start:a.value.span.end].strip()
                 for a in node.attributes)
    result = '\n'.join(parts).replace('\r\n', '\n')
    return re.sub(r'\{\s*("(?:[^"\\]|\\.)*")\s*\}', lambda m: json.loads(m[1]), result)


class Catalog:
    def __init__(self, root, source='en-US', target='ru-RU'):
        self.root = Path(root).resolve()
        if source == target:
            raise EditorError('Исходная и целевая локали должны различаться.')
        for locale in (source, target):
            if not re.fullmatch(r'[A-Za-z0-9_-]+', locale):
                raise EditorError('Некорректное имя локали.')
        self.source_root = self.root / 'Resources/Locale' / source
        self.target_root = self.root / 'Resources/Locale' / target
        if not self.source_root.is_dir() or not self.target_root.is_dir():
            raise EditorError('Не найдены каталоги локализации проекта.')
        self.source, self.target = source, target
        self.lock = threading.RLock()
        self.refresh()

    def read_file(self, path, base):
        if not path.resolve().is_relative_to(base.resolve()):
            raise EditorError('Файл выходит за пределы каталога локали.')
        raw = path.read_bytes() if path.exists() else b''
        text = raw.decode('utf-8-sig')
        nodes = {}
        errors = []
        for node in parse(text).body:
            if isinstance(node, ast.Junk):
                line = text[:node.span.start].count('\n') + 1
                errors.append(f'{path.relative_to(base)}:{line}: ' + '; '.join(a.message for a in node.annotations))
            elif isinstance(node, (ast.Message, ast.Term)):
                key = key_of(node)
                if key in nodes:
                    errors.append(f'{path.relative_to(base)}: повтор ключа {key}')
                nodes[key] = node
        return {'path': path, 'raw': raw, 'text': text, 'nodes': nodes, 'errors': errors}

    def scan(self, base):
        entries, files, errors = {}, {}, []
        for path in sorted(base.rglob('*.ftl')):
            file = self.read_file(path, base)
            files[path] = file
            errors.extend(file['errors'])
            for key, node in file['nodes'].items():
                if key in entries:
                    errors.append(f'Повтор ключа {key}: {path.relative_to(base)}')
                entries[key] = (file, node)
        return entries, files, errors

    def refresh(self):
        with self.lock:
            self.en, self.enfiles, en_errors = self.scan(self.source_root)
            self.ru, self.rufiles, ru_errors = self.scan(self.target_root)
            self.prototypes, entity_errors = scan_entities(self.root)
            self.entity_info = {}
            self.entity_dependencies = {}
            self.add_entity_sources()
            self.errors = en_errors + ru_errors
            self.warnings = entity_errors
            self.rows = []
            self.counts = dict(missing=0, same=0, different=0, extra=0)
            for key in sorted(self.en.keys() | self.ru.keys()):
                en, ru = self.en.get(key), self.ru.get(key)
                if not en:
                    status = 'extra'
                elif not ru:
                    status = 'missing'
                else:
                    enattrs = {a.id.name for a in en[1].attributes}
                    ruattrs = {a.id.name for a in ru[1].attributes}
                    if not enattrs <= ruattrs or (en[1].value is not None and ru[1].value is None):
                        status = 'missing'
                    else:
                        status = 'same' if pattern_text(en[0]['text'], en[1]) == pattern_text(ru[0]['text'], ru[1]) else 'different'
                record = en or ru
                base = self.source_root if en else self.target_root
                path = record[0]['path'].relative_to(base).as_posix()
                source = entry_text(en[0]['text'], en[1]) if en else ''
                target = entry_text(ru[0]['text'], ru[1]) if ru else ''
                entity = self.entity_info.get(key, [])
                context = ' '.join(p['id'] + ' ' + p['path'].relative_to(self.root).as_posix() for p in entity)
                self.rows.append({'key': key, 'file': path, 'status': status,
                                  'kind': 'entity' if entity or key.startswith('ent-') else 'message',
                                  'preview': (target or source).split('=', 1)[-1].strip()[:160],
                                  '_search': (key + '\n' + path + '\n' + source + '\n' + target + '\n' + context).casefold()})
                self.counts[status] += 1

    def add_entity_sources(self):
        original = dict(self.en)
        hashes = {}
        resolved = {}

        def resolve(ident, field):
            cache_key = (ident, field)
            if cache_key in resolved:
                return resolved[cache_key]
            queue, visited, deps = [ident], set(), set()
            value = None
            # Match PrototypeManager.EnumerateParents: breadth-first, not DFS.
            for ancestor in queue:
                if ancestor in visited or ancestor not in self.prototypes:
                    continue
                visited.add(ancestor)
                proto = self.prototypes[ancestor]
                deps.add(proto['path'])
                source = original.get(proto['key'])
                if source:
                    file, node = source
                    deps.add(file['path'])
                    pattern = node.value if field == 'name' else next(
                        (a.value for a in node.attributes if a.id.name == {'description': 'desc', 'suffix': 'suffix'}[field]), None)
                    if pattern is not None:
                        value = file['text'][pattern.span.start:pattern.span.end]
                if value is None and field in proto['fields']:
                    value = literal(proto['fields'][field])
                if value is not None:
                    break
                queue.extend(proto['parents'])
            resolved[cache_key] = (value, deps)
            return value, deps

        for proto in self.prototypes.values():
            self.entity_info.setdefault(proto['key'], []).append(proto)
        for key, protos in self.entity_info.items():
            proto = protos[0]
            existing = original.get(key)
            text = entry_text(existing[0]['text'], existing[1]) if existing else key + ' ='
            attrs = {a.id.name for a in existing[1].attributes} if existing else set()
            deps = {p['path'] for p in protos}
            for field, attr in (('name', None), ('description', 'desc'), ('suffix', 'suffix')):
                value, field_deps = resolve(proto['id'], field)
                deps.update(field_deps)
                if value is None:
                    continue
                if attr is None and (not existing or existing[1].value is None):
                    eq = text.index('=')
                    text = text[:eq + 1] + ' ' + value + text[eq + 1:]
                elif attr and attr not in attrs:
                    text += '\n    .' + attr + ' = ' + value
            if text == key + ' =':
                text += ' { "" }'
            resource = parse(text)
            if any(isinstance(n, ast.Junk) for n in resource.body):
                # Never silently hide an entity whose source cannot be represented.
                raise EditorError('Не удалось подготовить Fluent для entity ' + proto['id'])
            node = next(n for n in resource.body if isinstance(n, ast.Message))
            relative = proto['relative']
            if relative.parts[0] == 'Entities':
                relative = Path(*relative.parts[1:])
            path = existing[0]['path'] if existing else self.source_root / 'Entities' / relative.with_suffix('.ftl')
            virtual = dict(path=path, raw=text.encode('utf-8'), text=text, nodes={key: node}, errors=[], virtual=True)
            if existing and existing[1].comment:
                comment = existing[1].comment
                virtual['comment'] = existing[0]['text'][comment.span.start:comment.span.end]
            self.en[key] = (virtual, node)
            self.entity_dependencies[key] = {}
            for dep in deps:
                if dep not in hashes:
                    hashes[dep] = digest(dep.read_bytes())
                self.entity_dependencies[key][dep] = hashes[dep]

    def listing(self, query):
        with self.lock:
            search = query.get('q', [''])[0].casefold()
            status = query.get('status', ['all'])[0]
            folder = query.get('folder', [''])[0]
            kind = query.get('kind', ['all'])[0]
            scope = [r for r in self.rows if kind == 'all' or r['kind'] == kind]
            counts = {status: sum(r['status'] == status for r in scope) for status in self.counts}
            offset = max(0, int(query.get('offset', ['0'])[0]))
            rows = [r for r in scope if (status == 'all' or r['status'] == status)
                    and (not folder or r['file'].startswith(folder)) and search in r['_search']]
            return {'rows': [{k: v for k, v in r.items() if not k.startswith('_')} for r in rows[offset:offset + 80]],
                    'total': len(rows), 'counts': counts, 'errors': self.errors, 'warnings': self.warnings,
                    'folders': sorted({r['file'].split('/')[0] + '/' for r in self.rows if '/' in r['file']}),
                    'source': self.source, 'target': self.target}

    def detail(self, key):
        with self.lock:
            en, ru = self.en.get(key), self.ru.get(key)
            if not en and not ru:
                raise EditorError('Ключ не найден. Обновите список.', 404)
            path = ru[0]['path'] if ru else self.target_root / en[0]['path'].relative_to(self.source_root)
            file = self.read_file(path, self.target_root)
            node = file['nodes'].get(key)
            dependencies = self.entity_dependencies.get(key, {})
            if any(digest(path.read_bytes()) != version for path, version in dependencies.items()):
                raise EditorError('Прототип или его исходный перевод изменился. Нажмите «Перечитать файлы».', 409)
            enfile = (en[0] if en[0].get('virtual') else self.read_file(en[0]['path'], self.source_root)) if en else None
            ennode = enfile['nodes'].get(key) if enfile else None
            source = entry_text(enfile['text'], ennode) if ennode else ''
            target = entry_text(file['text'], node) if node else ''
            comment = enfile['text'][ennode.comment.span.start:ennode.comment.span.end] if ennode and ennode.comment else ''
            if enfile:
                comment = enfile.get('comment', comment)
            return {'key': key, 'source': source, 'target': target,
                    'file': path.relative_to(self.root).as_posix(), 'comment': comment,
                    'version': digest(file['raw']), 'sourceVersion': digest(enfile['raw']) if enfile else '',
                    'entity': [{'id': p['id'], 'path': p['path'].relative_to(self.root).as_posix(),
                                'parents': p['parents'], 'abstract': p['abstract']} for p in self.entity_info.get(key, [])],
                    'variables': sorted(set(VARIABLE.findall(source))), 'errors': file['errors']}

    def save(self, data):
        with self.lock:
            key, translation = data.get('key'), data.get('text')
            if not isinstance(key, str) or not isinstance(translation, str):
                raise EditorError('Нужны ключ и текст перевода.')
            current = self.detail(key)
            if current['version'] != data.get('version') or current['sourceVersion'] != data.get('sourceVersion'):
                raise EditorError('Файл изменился на диске. Откройте запись заново и объедините изменения.', 409)
            if self.errors:
                raise EditorError('В каталоге есть ошибки или дубликаты. Исправьте их и обновите индекс перед сохранением.')
            translation = translation.strip('\r\n')
            body = parse(translation).body
            if len(body) != 1 or not isinstance(body[0], (ast.Message, ast.Term)) or body[0].comment:
                raise EditorError('Введите одну запись Fluent без комментариев. Проверьте скобки и отступы.')
            node = body[0]
            if key_of(node) != key:
                raise EditorError('Нельзя изменять имя ключа.')
            attrs = [a.id.name for a in node.attributes]
            if len(attrs) != len(set(attrs)):
                raise EditorError('Атрибуты не должны повторяться.')
            # Preserve target-only attributes as well as the source contract.
            for template in (current['source'], current['target']):
                if not template:
                    continue
                original = next(n for n in parse(template).body if isinstance(n, (ast.Message, ast.Term)))
                missing = {a.id.name for a in original.attributes} - set(attrs)
                if missing or (original.value is not None and node.value is None):
                    raise EditorError('Нельзя удалять значение или атрибуты записи: ' + ', '.join(sorted(missing)))
            missing_vars = set(VARIABLE.findall(current['source'])) - set(VARIABLE.findall(translation))
            added_vars = set(VARIABLE.findall(translation)) - set(VARIABLE.findall(current['source'] + current['target']))
            if missing_vars or added_vars:
                raise EditorError('Проверьте переменные. Пропущены: ' + ', '.join(sorted(missing_vars))
                                  + '; неизвестные: ' + ', '.join(sorted(added_vars)))
            path = self.root / current['file']
            file = self.read_file(path, self.target_root)
            old = file['nodes'].get(key)
            newline = '\r\n' if b'\r\n' in file['raw'] else '\n'
            translation = translation.replace('\r\n', '\n').replace('\n', newline)
            node = parse(translation).body[0]
            if old:
                result = file['text'][:old.id.span.start] + translation + file['text'][old.span.end:]
            else:
                result = file['text'] + (newline * 2 if file['text'] else '') + translation + newline
            if any(isinstance(n, ast.Junk) for n in parse(result).body):
                raise EditorError('Изменение нарушает синтаксис файла.')
            payload = (b'\xef\xbb\xbf' if file['raw'].startswith(b'\xef\xbb\xbf') else b'') + result.encode('utf-8')
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as temp:
                    temp_path = Path(temp.name)
                    temp.write(payload)
                    temp.flush()
                    os.fsync(temp.fileno())
                if digest(path.read_bytes() if path.exists() else b'') != current['version']:
                    raise EditorError('Файл изменился во время сохранения. Повторно откройте запись.', 409)
                os.replace(temp_path, path)
            finally:
                if temp_path and temp_path.exists():
                    temp_path.unlink()
            # Reindex the changed file only; a full scan remains an explicit action.
            updated = self.read_file(path, self.target_root)
            self.rufiles[path] = updated
            for updated_key, updated_node in updated['nodes'].items():
                self.ru[updated_key] = (updated, updated_node)
            row = next(r for r in self.rows if r['key'] == key)
            self.counts[row['status']] -= 1
            source = current['source']
            row['status'] = ('same' if source and pattern_text(source, parse(source).body[0]) == pattern_text(translation, node)
                             else 'different' if source else 'extra')
            self.counts[row['status']] += 1
            row['preview'] = translation.split('=', 1)[-1].strip()[:160]
            row['_search'] = (key + '\n' + row['file'] + '\n' + source + '\n' + translation).casefold()
            row['_search'] += ' ' + ' '.join(p['id'] + ' ' + p['path'].relative_to(self.root).as_posix()
                                           for p in self.entity_info.get(key, [])).casefold()
            return self.detail(key)


def make_server(catalog, port=0):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, status, data, content_type='application/json; charset=utf-8'):
            payload = json.dumps(data, ensure_ascii=False).encode('utf-8') if isinstance(data, (dict, list)) else data
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def allowed_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def do_GET(self):
            if not self.allowed_host():
                return self.respond(403, {'error': 'Недопустимый адрес сервера.'})
            url = urlsplit(self.path)
            try:
                if url.path == '/api/entries':
                    return self.respond(200, catalog.listing(parse_qs(url.query)))
                if url.path == '/api/entry':
                    return self.respond(200, catalog.detail(parse_qs(url.query).get('key', [''])[0]))
                if url.path == '/api/session':
                    return self.respond(200, {'token': token})
                assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                          '/style.css': ('style.css', 'text/css; charset=utf-8')}
                if url.path in assets:
                    name, mime = assets[url.path]
                    return self.respond(200, (HERE / name).read_bytes(), mime)
                self.respond(404, {'error': 'Не найдено.'})
            except (EditorError, ValueError, OSError) as exc:
                self.respond(getattr(exc, 'status', 400), {'error': str(exc)})

        def do_POST(self):
            origin = f'http://127.0.0.1:{self.server.server_port}'
            if (not self.allowed_host() or self.headers.get('Origin') != origin
                    or not secrets.compare_digest(self.headers.get('X-Editor-Token', ''), token)):
                return self.respond(403, {'error': 'Запрос разрешён только из окна редактора.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 512_000:
                    raise EditorError('Недопустимый размер запроса.', 413)
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise EditorError('Ожидается объект JSON.')
                if self.path == '/api/save':
                    return self.respond(200, catalog.save(data))
                if self.path == '/api/refresh':
                    catalog.refresh()
                    return self.respond(200, {'ok': True})
                self.respond(404, {'error': 'Не найдено.'})
            except (EditorError, ValueError, OSError) as exc:
                self.respond(getattr(exc, 'status', 400), {'error': str(exc)})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description='Локальный редактор локализации Fluent')
    cli.add_argument('--root', type=Path, default=HERE.parents[1])
    cli.add_argument('--source', default='en-US')
    cli.add_argument('--target', default='ru-RU')
    cli.add_argument('--port', type=int, default=0)
    cli.add_argument('--open', action='store_true')
    args = cli.parse_args()
    print('Чтение файлов локализации…', flush=True)
    server = make_server(Catalog(args.root, args.source, args.target), args.port)
    address = f'http://127.0.0.1:{server.server_port}'
    print(f'Редактор: {address}\nДля остановки нажмите Ctrl+C.', flush=True)
    if args.open:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
