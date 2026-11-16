import ast
import inspect
import unittest
from web_scraping_claim_audit import phrases

class PhraseOracle(unittest.TestCase):
    def test_exact_vocabulary(self):
        tree = ast.parse(inspect.getsource(phrases))
        actual = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)}
        self.assertEqual(actual, {'WEBSCRAPING': ('web scraping', 'scrapes websites', 'scrape websites', 'scrapes web pages', 'scrape web pages', 'scrapes the web', 'scrape the web', 'scrapes data from websites', 'scrape data from websites', 'scrapes data from web pages', 'scrape data from web pages', 'scrapes any website', 'scrape any website', 'scrapes any web page', 'scrapes product listings', 'scrape product listings', 'scrapes prices', 'scrape prices', 'scrapes search results', 'scrapes job listings', 'scrapes real estate listings', 'scrapes reviews', 'scrape reviews', 'scrapes news articles', 'scrapes tables from web pages', 'extracts data from websites', 'extract data from websites', 'extracts data from web pages', 'extract data from web pages', 'extracts structured data from websites', 'harvests data from websites', 'crawls websites', 'crawl websites', 'crawls web pages', 'crawl web pages', 'crawls the web', 'crawls any website', 'web crawler', 'crawls and extracts data', 'scrapes content from websites', 'scrape content from websites', 'scrapes content from web pages', 'scrapes images from websites', 'scrapes links from web pages', 'scrapes multiple websites', 'automatically scrapes websites', 'scrapes live data from websites', 'scrapes public websites', 'scrapes public web pages', 'web scraper'), 'NOWEBSCRAPING': ('no web scraping', 'does not scrape websites', 'never scrapes websites', 'does not scrape web pages', 'never scrapes web pages', 'does not scrape the web', 'never scrapes the web', 'no web scraper', 'does not crawl websites', 'never crawls websites', 'does not crawl web pages', 'never crawls web pages', 'does not scrape data from websites', 'never scrapes data from websites', 'does not extract data from websites', 'never extracts data from websites', 'no web crawler', 'does not scrape prices', 'never scrapes prices', 'does not scrape reviews', 'never scrapes reviews', 'does not scrape content from websites', 'never scrapes content from websites', 'web scraping not supported'), 'GENERIC_NAMES': ('scrape_page', 'scrape_website', 'scrape_site', 'scrape_url', 'scrape_webpage', 'scrape_listing', 'scrape_listings', 'scrape_product', 'scrape_products', 'scrape_prices', 'extract_listings', 'crawl_site', 'crawl_website', 'crawl_page', 'crawl_pages', 'fetch_and_parse', 'scrape_data', 'scrape_content', 'scrape_table', 'scrape_images', 'scrape_reviews', 'scrape_jobs', 'web_scrape', 'scrape_search_results')})

import contextlib
import io
import json
import tempfile
from pathlib import Path
from web_scraping_claim_audit.audit import audit, claims, evidence, normalize
from web_scraping_claim_audit.__main__ import main

SOUP = 'from bs4 import BeautifulSoup\nsoup = BeautifulSoup(data)\nsoup.find("a")\n'
FETCH = 'import requests\nrequests.get(url)\n'

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
    def put(self, path, text):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    def cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            code = main(list(args))
        return code, out.getvalue()
    def test_pass(self):
        self.put('README.md', 'scrapes websites')
        self.put('app.py', FETCH + SOUP)
        self.assertEqual(self.cli('audit', str(self.root))[0], 0)
    def test_claim_only(self):
        self.put('README.md', 'scrapes websites')
        code, output = self.cli('audit', str(self.root), '--json')
        self.assertEqual(code, 2)
        result = json.loads(output)
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertEqual(result['findings'][0]['id'], 'documented-web-scraping-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        self.assertTrue(result['findings'][0]['message'])
    def test_denial(self):
        self.put('README.md', 'no web scraping')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')
        self.put('app.py', FETCH + SOUP)
        self.assertEqual(audit(self.root)['findings'][0]['id'], 'documented-no-web-scraping-claim-false')
        self.assertEqual(self.cli('audit', str(self.root))[0], 2)
    def test_no_claim(self):
        self.put('app.py', FETCH + SOUP)
        self.assertEqual(audit(self.root)['verdict'], 'PASS')
    def test_test_only(self):
        self.put('README.md', 'web scraping')
        for path in ['tests/app.py', 'test_app.py', 'app_test.py']:
            with self.subTest(path=path):
                self.put(path, FETCH + SOUP)
                self.assertEqual(audit(self.root)['findings'][0]['severity'], 'MEDIUM')
        self.assertEqual(self.cli('audit', str(self.root))[0], 0)
        self.assertEqual(self.cli('audit', str(self.root), '--fail-on', 'medium')[0], 2)
    def test_exclusions(self):
        for component in ['docs', 'fixtures', 'examples']:
            self.put(component + '/app.py', FETCH + SOUP)
        self.assertFalse(audit(self.root)['evidence'])
    def test_symlinks(self):
        self.put('fixtures/app.py', FETCH + SOUP)
        (self.root/'linked.py').symlink_to(self.root/'fixtures/app.py')
        (self.root/'linked').symlink_to(self.root/'fixtures', target_is_directory=True)
        self.assertFalse(audit(self.root)['evidence'])
    def test_split(self):
        for a,b in [(FETCH, SOUP), ('page.goto(url)', 'page.locator("a")'), ('driver.get(url)', 'driver.find_element("a")'), ('import scrapy\nclass X(scrapy.Spider): pass', 'response.css("a")')]:
            self.put('a.py', a)
            self.put('b.py', b)
            self.assertFalse(audit(self.root)['evidence'])
    def test_ignore(self):
        self.put('src/app.py', FETCH + SOUP)
        self.assertFalse(audit(self.root, ['src'])['evidence'])
        self.assertTrue(audit(self.root, ['sr'])['evidence'])
        self.assertEqual(self.cli('audit', str(self.root), '--ignore', 'src', '--ignore', 'other')[0], 0)
    def test_docs(self):
        self.put('nested/docs/a.md', '`web scraping`')
        self.put('OTHER.md', 'no web scraping')
        self.assertEqual(len(audit(self.root)['findings']), 1)
    def test_errors(self):
        self.assertEqual(self.cli('audit', str(self.root/'missing'))[0], 1)
        for args in [[], ['bad'], ['audit', '--fail-on', 'HIGH'], ['audit', '--ignore', 'a', 'b', 'c']]:
            with self.subTest(args=args), self.assertRaises(SystemExit) as exc:
                self.cli(*args)
            self.assertEqual(exc.exception.code, 1)
    def test_version(self):
        with contextlib.redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as exc:
            main(['--version'])
        self.assertEqual(exc.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), '0.1.0')
    def test_self_audit(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(claims((root/'README.md').read_text()), ([], []))
        self.assertEqual(audit(root)['verdict'], 'PASS')

class MatchingTests(unittest.TestCase):
    def test_all_phrases(self):
        for phrase in phrases.WEBSCRAPING:
            self.assertEqual(claims(phrase), ([phrase], []))
        for phrase in phrases.NOWEBSCRAPING:
            self.assertEqual(claims(phrase), ([], [phrase]))
    def test_normalization(self):
        self.assertEqual(normalize("DOESN'T  scrape-websites"), 'does not scrape websites')
        self.assertEqual(claims("doesn't scrape-websites"), ([], ['does not scrape websites']))
        self.assertEqual(claims('web\n scraping'), (['web scraping'], []))
        self.assertEqual(claims('web\n\n scraping'), ([], []))
    def test_boundaries(self):
        for text in ['web scrapers', 'web crawlers', 'scraping websites', 'scrape a website', 'generate html', 'extract invoices', 'xweb scrapingx']:
            self.assertEqual(claims(text), ([], []))
    def test_fences(self):
        for fence in ['```', '~~~', '   ````']:
            self.assertEqual(claims(fence+'\nweb scraping\n'+fence), ([], []))
        self.assertEqual(claims('`web scraping`'), (['web scraping'], []))
    def test_longest(self):
        self.assertEqual(claims('automatically scrapes websites'), (['automatically scrapes websites'], []))
        self.assertEqual(claims('no web scraping; web scraper'), (['web scraper'], ['no web scraping']))

class EvidenceTests(unittest.TestCase):
    def test_fetch_forms(self):
        forms = ['import requests\nrequests.get(url)', 'import requests as r\nr.request("GET", url)', 'from requests import get as g\ng(url)', 'from requests import request\nrequest("GET", url)', 'import requests\ns = requests.Session()\ns.get(url)', 'from requests import Session as S\ns: object = S()\ns.get(url)', 'import httpx\nhttpx.get(url)', 'import httpx as h\nwith h.Client() as c:\n c.get(url)', 'from httpx import get as g\ng(url)', 'import urllib.request\nurllib.request.urlopen(url)', 'import urllib.request as u\nu.urlopen(url)', 'from urllib.request import urlopen as op\nop(url)', 'import httpx\nasync def f():\n async with httpx.AsyncClient() as c:\n  c.get(url)']
        for form in forms:
            with self.subTest(form=form):
                self.assertTrue(evidence(form+'\n'+SOUP))
    def test_soup_forms(self):
        for construction in ['from bs4 import BeautifulSoup as B\ns = B(data)', 'import bs4\ns = bs4.BeautifulSoup(data)', 'import bs4 as b\ns = b.BeautifulSoup(data)']:
            for method in ['find', 'find_all', 'select']:
                self.assertTrue(evidence(FETCH+construction+'\ns.'+method+'("a")'))
    def test_lxml(self):
        for construction in ['import lxml.html\nx = lxml.html.fromstring(data)', 'from lxml import html as h\nx = h.fromstring(data)', 'from lxml.html import fromstring as f\nx = f(data)', 'from lxml import etree\nx = etree.HTML(data)', 'from lxml.etree import HTML\nx = HTML(data)']:
            self.assertTrue(evidence(FETCH+construction+'\nx.xpath("a")'))
    def test_scrapy(self):
        for form in ['import scrapy\nclass X(scrapy.Spider): pass', 'import scrapy.spiders\nclass X(scrapy.spiders.Spider): pass', 'from scrapy import Spider as S\nclass X(S): pass', 'import scrapy as s\ns.Request(url)', 'from scrapy import Request as R\nR(url)', 'from scrapy.http import FormRequest as F\nF(url)', 'import scrapy.http as h\nh.FormRequest(url)']:
            for method in ['css', 'xpath']:
                self.assertTrue(evidence(form+'\nresponse.'+method+'("a")'))
    def test_browser_pairs(self):
        for method in ['locator', 'query_selector', 'query_selector_all', 'inner_text', 'content']:
            self.assertTrue(evidence('p.goto(url)\np.'+method+'()'))
        for method in ['find_element', 'find_elements']:
            self.assertTrue(evidence('d.get(url)\nd.'+method+'()'))
    def test_generic(self):
        for name in phrases.GENERIC_NAMES:
            for form in ['x.'+name+'()', 'from package import '+name+'\n'+name+'()', 'from package import '+name+' as alias\nalias()']:
                self.assertTrue(evidence(form), form)
            self.assertFalse(evidence(name+'()'))
            self.assertFalse(evidence('from package import '+name+'\ndef '+name+'(): pass\n'+name+'()'))
            self.assertFalse(evidence('class C:\n def '+name+'(self): pass\nx.'+name+'()'))
    def test_negative(self):
        cases = [FETCH, 'import httpx\nhttpx.get(url)', 'from urllib.request import urlopen\nurlopen(url)', 'from bs4 import BeautifulSoup', SOUP, SOUP.replace('data', 'open("x.html").read()'), 'from bs4 import BeautifulSoup\nBeautifulSoup(data).prettify()', 'import lxml.html\nlxml.html.fromstring(data).xpath("a")', 'feedparser.parse(data)', 'sitemap.parse(data)', 'import requests\nrequests.get("robots.txt")', 'subprocess.run(["curl", url])', 'subprocess.run(["wget", url])', 'import scrapy\nclass X(scrapy.Spider): pass', 'import scrapy\nscrapy.Request(url)', 'p.goto(url)', 'p.locator("a")', 'd.get(url)', 'd.find_element("a")', 're.findall(pattern, open("x.html").read())', 'import html.parser\nhtml.parser.HTMLParser()', 'html5lib.parse(data)', '"scrape crawl web scraping"', 'mindee.parse(InvoiceV4)', 'azure.begin_analyze_document("prebuilt-layout")', 'veryfi.Client()', 'documentai.process_document(data)', 'textract.analyze_document(data)', 'eden.universal_ai(data)', 'LlamaParse().load_data(data)', 'nanonets.ocr(model_id)', 'docsumo.upload(data)', 'abbyy.process(data)', 'rossum.upload(data)', 'klippa.parse(data)', 'parseur.upload(data)', 'extend.process(data)', 'import requests\ndef requests(): pass\nrequests.get(url)\n'+SOUP, 'from bs4 import BeautifulSoup\nclass BeautifulSoup: pass\n'+FETCH+'BeautifulSoup(data).find("a")', 'd.get(url)\n'+SOUP, 'not valid @@@', 'import package\npackage.scrape_page', 'import bs4\nstr(soup)', 'import lxml.etree\nlxml.etree.tostring(tree)']
        for source in cases:
            with self.subTest(source=source):
                self.assertFalse(evidence(source))

class EntryPointTests(unittest.TestCase):
    def test_module_entry_point(self):
        import subprocess
        import sys
        result = subprocess.run([sys.executable, '-m', 'web_scraping_claim_audit', '--version'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), '0.1.0')
