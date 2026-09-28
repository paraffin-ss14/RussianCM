import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import Catalog, EditorError, make_server


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.en = self.root / 'Resources/Locale/en-US'
        self.ru = self.root / 'Resources/Locale/ru-RU'
        self.en.mkdir(parents=True)
        self.ru.mkdir(parents=True)
        (self.en / 'source.ftl').write_text(
            '#Context\nhello = Hello { $name }\n    .desc = Description\n'
            'same = Same\nmissing = Missing\n-part = Term\n'
            'dialect = { -part(state: $state) }\n', encoding='utf-8')
        (self.ru / 'elsewhere.ftl').write_bytes(
            b'\xef\xbb\xbf' + '# Комментарий\r\nhello = Привет { $name }\r\n    .desc = Описание\r\n'
            'same = Same\r\nextra = Лишний\r\n'.encode('utf-8'))
        self.catalog = Catalog(self.root)

    def save(self, key, text, detail=None):
        return self.catalog.save({**(detail or self.catalog.detail(key)), 'text': text})

    def test_global_matching_search_and_status(self):
        listing = self.catalog.listing({})
        self.assertEqual(listing['counts'], dict(missing=3, same=1, different=1, extra=1))
        self.assertEqual(self.catalog.listing({'q': ['привет']})['rows'][0]['key'], 'hello')
        self.assertEqual(self.catalog.errors, [])

    def test_save_preserves_comments_bom_crlf_neighbors_and_source(self):
        source = (self.en / 'source.ftl').read_bytes()
        before = (self.ru / 'elsewhere.ftl').read_bytes()
        old = 'hello = Привет { $name }\r\n    .desc = Описание'.encode()
        new = 'hello = Здравствуйте { $name }\r\n    .desc = Новое описание'.encode()
        self.save('hello', new.decode())
        self.assertEqual((self.ru / 'elsewhere.ftl').read_bytes(), before.replace(old, new))
        self.assertEqual((self.en / 'source.ftl').read_bytes(), source)
        self.assertFalse((self.ru / 'source.ftl').exists())

    def test_missing_entry_creates_matching_file(self):
        self.save('missing', 'missing = Отсутствует')
        self.assertEqual((self.ru / 'source.ftl').read_text(encoding='utf-8'), 'missing = Отсутствует\n')
        self.assertEqual(self.catalog.counts['missing'], 2)
        self.assertEqual(self.catalog.counts['different'], 2)

    def test_invalid_saves_do_not_write(self):
        path = self.ru / 'elsewhere.ftl'
        before = path.read_bytes()
        invalid = ['other = Изменённый ключ', 'hello = {',
                   'hello = Без переменной\n    .desc = Описание',
                   'hello = { $name }', 'hello = { $name }\n    .desc = { $unknown }',
                   'hello = { $name }\n    .desc = x\n    .desc = y',
                   'hello = { $name }\n    .desc = x\ninjected = x']
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(EditorError):
                self.save('hello', text)
            self.assertEqual(path.read_bytes(), before)

    def test_conflict_on_changed_source_or_target(self):
        for path in (self.ru / 'elsewhere.ftl', self.en / 'source.ftl'):
            detail = self.catalog.detail('hello')
            path.write_bytes(path.read_bytes() + b'\n# External change\n')
            with self.assertRaises(EditorError) as exc:
                self.save('hello', 'hello = Hi { $name }\n    .desc = Detail', detail)
            self.assertEqual(exc.exception.status, 409)

    def test_russian_plural_and_named_argument(self):
        self.save('dialect', 'dialect = { $state ->\n    [one] Один\n    [few] Несколько\n   *[other] { -part(state: $state) }\n}')
        self.assertEqual(self.catalog.detail('dialect')['variables'], ['$state'])

    def test_partial_entry_requires_attributes(self):
        (self.ru / 'elsewhere.ftl').write_text('hello = Привет { $name }\n', encoding='utf-8')
        self.catalog.refresh()
        self.assertEqual(self.catalog.counts['missing'], 5)
        self.save('hello', 'hello = Привет { $name }\n    .desc = Описание')
        self.assertEqual(self.catalog.counts['missing'], 4)

    def test_duplicate_key_blocks_save(self):
        (self.ru / 'duplicate.ftl').write_text('hello = Дубликат\n', encoding='utf-8')
        self.catalog.refresh()
        with self.assertRaises(EditorError):
            self.save('same', 'same = То же')

    def entities(self):
        base = self.root / 'Resources/Prototypes/Test'
        base.mkdir(parents=True)
        path = base / 'items.yml'
        path.write_text('- type: entity\n  id: BaseItem\n  abstract: true\n  name: base item\n'
                        '  description: Base description\n  suffix: Debug\n'
                        '- type: entity\n  id: ChildItem\n  parent: BaseItem\n  name: child item\n'
                        '  components:\n  - type: Test\n    effect: !type:SomeEffect {}\n', encoding='utf-8')
        return path

    def test_entity_yaml_inheritance_save_and_original_preservation(self):
        yaml_path = self.entities()
        before = yaml_path.read_bytes()
        self.catalog.refresh()
        detail = self.catalog.detail('ent-ChildItem')
        self.assertIn('child item', detail['source'])
        self.assertIn('Base description', detail['source'])
        self.assertIn('.suffix', detail['source'])
        self.assertEqual(detail['entity'][0]['parents'], ['BaseItem'])
        self.save('ent-ChildItem', 'ent-ChildItem = Предмет\n    .desc = Описание\n    .suffix = Отладка')
        self.assertEqual(yaml_path.read_bytes(), before)
        self.assertTrue((self.ru / 'Entities/Test/items.ftl').exists())
        self.assertEqual(self.catalog.listing({'kind': ['entity'], 'status': ['different']})['total'], 1)

    def test_entity_existing_translation_in_other_file_and_en_override(self):
        self.entities()
        (self.en / 'entity.ftl').write_text('ent-BaseItem = FTL base\n    .desc = FTL description\n', encoding='utf-8')
        (self.ru / 'custom.ftl').write_text('ent-ChildItem = Предмет\n', encoding='utf-8')
        self.catalog.refresh()
        detail = self.catalog.detail('ent-ChildItem')
        self.assertIn('FTL description', detail['source'])
        self.assertTrue(detail['file'].endswith('custom.ftl'))
        self.assertEqual(self.catalog.listing({'q':['ChildItem'], 'kind':['entity'], 'status':['missing']})['total'], 1)

    def test_entity_parent_change_requires_refresh(self):
        path = self.entities()
        self.catalog.refresh()
        detail = self.catalog.detail('ent-ChildItem')
        path.write_bytes(path.read_bytes() + b'\n# Changed parent\n')
        with self.assertRaises(EditorError) as exc:
            self.save('ent-ChildItem', detail['source'], detail)
        self.assertEqual(exc.exception.status, 409)

    def test_entity_cmu_custom_localization_id_and_literal_braces(self):
        base = self.root / 'Content.CMU/Resources/Prototypes/CMU14'
        base.mkdir(parents=True)
        (base / 'custom.yml').write_text('- type: entity\n  id: Custom\n  localizationId: custom-entity\n'
                                       '  name: \'Tool {special} "quoted"\'\n', encoding='utf-8')
        self.catalog.refresh()
        detail = self.catalog.detail('custom-entity')
        self.assertIn('CMU14/custom.ftl', detail['file'])
        self.assertEqual(self.catalog.listing({'kind':['entity']})['total'], 1)
        self.save('custom-entity', 'custom-entity = Инструмент')

    def test_entity_same_yaml_literal_and_plain_ftl(self):
        self.entities()
        (self.ru / 'entity.ftl').write_text('ent-ChildItem = child item\n    .desc = Base description\n    .suffix = Debug\n', encoding='utf-8')
        self.catalog.refresh()
        self.assertEqual(self.catalog.listing({'kind':['entity'],'status':['same']})['total'], 1)

    def test_entity_variants_and_breadth_first_parent_order(self):
        path = self.entities()
        with path.open('a', encoding='utf-8') as file:
            file.write('- type: entity\n  id: SecondParent\n  description: Direct parent\n'
                       '- type: entity\n  id: !type:CreateVariants\n    values: [VariantA, VariantB]\n'
                       '  parent: [ChildItem, SecondParent]\n')
        self.catalog.refresh()
        for key in ('ent-VariantA', 'ent-VariantB'):
            self.assertIn('Direct parent', self.catalog.detail(key)['source'])
            self.assertNotIn('Base description', self.catalog.detail(key)['source'])

    def test_invalid_entity_warns_without_blocking_valid_entries(self):
        path = self.entities()
        with path.open('a', encoding='utf-8') as file:
            file.write('- type: entity\n  id: Invalid=\n  name: Invalid\n')
        self.catalog.refresh()
        self.assertTrue(self.catalog.warnings)
        self.assertFalse(self.catalog.errors)
        self.save('same', 'same = То же')

    def test_http_rejects_foreign_origin_missing_token_and_host(self):
        server = make_server(self.catalog)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = f'http://127.0.0.1:{server.server_port}'
        with urlopen(url + '/api/session') as response:
            token = json.load(response)['token']
        data = json.dumps({**self.catalog.detail('same'), 'text': 'same = То же'}).encode()
        for headers in ({}, {'Origin': 'https://example.com', 'X-Editor-Token': token},
                        {'Origin': url}, {'Origin': url, 'X-Editor-Token': token, 'Host': 'evil.example'}):
            with self.assertRaises(HTTPError) as exc:
                urlopen(Request(url + '/api/save', data, headers))
            self.assertEqual(exc.exception.code, 403)
            exc.exception.close()
        with urlopen(Request(url + '/api/save', data, {'Origin': url, 'X-Editor-Token': token})) as response:
            self.assertEqual(json.load(response)['target'], 'same = То же')
        with self.assertRaises(HTTPError) as exc:
            urlopen(url + '/../../server.py')
        exc.exception.close()


if __name__ == '__main__':
    unittest.main()
