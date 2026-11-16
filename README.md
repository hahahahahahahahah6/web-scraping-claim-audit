# Documentation claim auditor

An offline static auditor that compares documented capability statements with Python source patterns. It reads root README.md and Markdown beneath any docs directory, excludes fenced blocks, and counts inline code. It never executes inspected source, contacts a service, or changes the inspected repository. Runtime dependencies are limited to the standard library.

```text
web-scraping-claim-audit 0.1.0
```

## Install and use

Install a locally built distribution in an environment with pip available:

```sh
PIP_NO_INDEX=1 python3 -m pip install dist/web_scraping_claim_audit-0.1.0-py3-none-any.whl
web-scraping-claim-audit --version
web-scraping-claim-audit audit .
python3 -m web_scraping_claim_audit audit . --json
web-scraping-claim-audit audit . --verbose --ignore vendor --ignore archive --fail-on medium
```

The optional repository defaults to the current directory. Each ignore argument is one repository-relative directory or file prefix, matched at a path boundary. Severity thresholds are lowercase; the default is high. Exit status is 0 when no finding reaches the threshold, 2 when a finding reaches it, and 1 for usage or input errors. JSON includes verdict, findings with message and severity, production evidence paths, and test evidence paths. A medium finding remains visible even when the default threshold permits exit 0.

```text
documented-web-scraping-claim-false       HIGH: affirmative statement without production evidence
                                       MEDIUM: evidence only in tests
documented-no-web-scraping-claim-false    HIGH: denial with production evidence
```

Affirmative statements without any source produce a high finding; denials without source pass. One finding is emitted per applicable family. Matching lowercases text, expands negative contractions, converts hyphens to spaces, and collapses whitespace within paragraphs. Exact phrases use word boundaries and longest-first selection with alphabetical ties. Denial spans are removed before affirmative matching.

## Source patterns

The five library routes require all their parts within one module. Imports, aliases, constructor assignments, annotated assignments and context manager bindings are tracked. Local function, method and class definitions shadow matching route names. Generic operation names count as attribute calls or imported names, never unimported bare calls.

```text
requests / httpx / urllib.request fetch + bs4.BeautifulSoup + find / find_all / select
requests / httpx / urllib.request fetch + lxml.html.fromstring / lxml.etree.HTML + xpath
scrapy.Spider subclass or scrapy.Request / FormRequest + css / xpath
Playwright goto + locator / query_selector / query_selector_all / inner_text / content
Selenium get + find_element / find_elements
24 exact generic operation names are listed in web_scraping_claim_audit/phrases.py.
```

Test evidence is separate: paths containing tests, or filenames beginning test_ or ending _test.py. Source under fixtures, docs and examples is excluded. Symlinked files and directories and syntax-invalid modules provide no evidence. Source is parsed using the standard AST parser.

## Limitations

Static patterns are approximations rather than semantic judgement. Dead code counts; untraceable alias chains are missed. Operations divided between modules are missed. Exact vocabulary misses paraphrases, and denial handling depends on the fixed list.

Broad documented statements can describe monitoring, smoke testing, official JSON APIs, link checking, indexing, direct image downloads, user-pasted data aggregation or metasearch. These meanings can create false positives; only the source patterns decide whether evidence exists.

A bare HTTP fetch is insufficient because it may call a REST API. Construction plus selection without a fetch may parse local files or literal strings and is insufficient. A Spider or Request without css/xpath is insufficient. Browser navigation without selection, and selection without navigation, are insufficient. A Selenium driver.get plus BeautifulSoup find is missed: the fetch detector accepts only the listed requests/httpx/urlopen calls, while the Selenium route requires find_element(s). Cross-library pairing is deliberately unsupported.

Hand-written local-file reads with regular expressions, html.parser and html5lib alone have no accepted fingerprint. BeautifulSoup prettify, str(soup) and lxml tostring alone only re-emit existing markup. Feedparser alone reads RSS/Atom; sitemap parsing alone and robots.txt fetches alone are insufficient. Subprocess curl, wget and other external command calls are excluded.

Document extraction services provide no accepted route: Mindee with any product, Azure begin_analyze_document with any model, Veryfi with any call, Google Document AI process_document or batch_process_documents with any processor, Eden AI universal-ai with any model, Textract, LlamaParse, Nanonets, Docsumo, ABBYY Vantage, Rossum, Klippa, Parseur and Extend. Opaque model, skill, queue, template and workflow IDs and generic uploads cannot establish the checked operation.

Generation statements about HTML, PDF, spreadsheets, word documents, presentations, images or text are outside the vocabulary. Document extraction statements about invoices, receipts, identity documents, passports, checks, bank statements, tax forms, pay stubs, insurance cards, business cards, credit cards, contracts, mortgages, resumes, bills of lading, delivery notes, registration certificates, utility bills, marriage certificates, bank details, nutrition labels, material certificates, mail, health cards, driver licenses and vaccination cards are outside it, as are splitting, multiple-receipt detection and cropping statements.

## Development

```sh
python3 -m unittest discover
PIP_NO_INDEX=1 PIP_FIND_LINKS="$PWD/.verification/wheelhouse" python3 -m build
```

The source distribution includes the tests. Building requires a local wheelhouse containing the build requirements when isolation is enabled. The project uses the MIT license.
