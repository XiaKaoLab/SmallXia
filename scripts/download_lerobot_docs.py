"""功能：下载 LeRobot 中文文档正文，生成离线 HTML、Markdown 和来源清单。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import html
import json
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify


class DocumentationDownloader:
    base = 'https://hugging-face.cn'
    prefix = '/docs/lerobot/'

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def fetch(self, url):
        response = requests.get(url, timeout=45)
        response.raise_for_status()
        response.encoding = 'utf-8'
        return BeautifulSoup(response.text, 'html.parser')

    def links(self, soup, url):
        result = set()
        for anchor in soup.select('a[href]'):
            parsed = urlparse(urljoin(url, anchor['href']))
            if parsed.netloc == urlparse(self.base).netloc and parsed.path.startswith(self.prefix):
                result.add(self.base + parsed.path.rstrip('/'))
        return result

    def page(self, url):
        soup = self.fetch(url)
        body = soup.select_one('.prose-doc')
        if body is None or not body.select_one('h1'):
            raise ValueError('未找到文档正文')
        links = self.links(soup, url)
        slug = urlparse(url).path.removeprefix(self.prefix)
        name = slug.replace('/', '__') or 'index'
        title = body.select_one('h1').get_text(' ', strip=True)
        for node in body.select('script,style,button'):
            node.decompose()
        for anchor in body.select('a[href]'):
            target = urlparse(urljoin(url, anchor['href']))
            if target.netloc == urlparse(self.base).netloc and target.path.startswith(self.prefix):
                local = target.path.removeprefix(self.prefix).rstrip('/').replace('/', '__') or 'index'
                anchor['href'] = local + '.html' + ('#' + target.fragment if target.fragment else '')
            else:
                anchor['href'] = urljoin(url, anchor['href'])
        for image in body.select('img[src],video[src],source[src]'):
            image['src'] = urljoin(url, image['src'])
        content = str(body)
        self.root.joinpath(name + '.html').write_text(
            '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<style>body{max-width:960px;margin:40px auto;padding:0 24px;font:16px/1.8 system-ui}pre{overflow:auto;background:#f2f5f4;padding:16px}img,video{max-width:100%}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:8px}</style>'
            + '<title>' + html.escape(title) + '</title><a href="README.html">文档目录</a><p>来源：<a href="'
            + html.escape(url) + '">' + html.escape(url) + '</a></p>' + content, encoding='utf-8')
        for anchor in body.select('a[href]'):
            if not urlparse(anchor['href']).scheme:
                anchor['href'] = anchor['href'].replace('.html', '.md')
        self.root.joinpath(name + '.md').write_text('# 来源\n\n' + url + '\n\n' + markdownify(str(body), heading_style='ATX'), encoding='utf-8')
        return {'url': url, 'title': title, 'file': name}, links

    def run(self):
        pending = {self.base + self.prefix + 'index'}
        seen, pages, errors = set(), [], []
        with ThreadPoolExecutor(max_workers=5) as pool:
            while pending:
                batch = pending - seen
                if not batch:
                    break
                seen.update(batch)
                pending = set()
                futures = {pool.submit(self.page, url): url for url in sorted(batch)}
                for future in as_completed(futures):
                    url = futures[future]
                    try:
                        page, links = future.result()
                        pages.append(page)
                        pending.update(links - seen)
                    except Exception as error:
                        errors.append({'url': url, 'error': str(error)})
        pages.sort(key=lambda p: p['file'])
        # 源站失效链接保留远程地址，避免生成无法打开的本地链接。
        for page in pages:
            for extension in ('html', 'md'):
                path = self.root / (page['file'] + '.' + extension)
                content = path.read_text(encoding='utf-8')
                for error in errors:
                    slug = urlparse(error['url']).path.removeprefix(self.prefix).replace('/', '__')
                    content = content.replace(slug + '.' + extension, error['url'])
                path.write_text(content, encoding='utf-8')
        notice = '下载中文镜像站正文。图片、视频仍引用远程资源，离线观看文字不需要网络。站点为非官方镜像；外部模型、数据集及代码仓库不在下载范围。'
        self.root.joinpath('README.md').write_text('# LeRobot 中文文档\n\n' + notice + '\n\n' + '\n'.join(f"- [{p['title']}]({p['file']}.md)" for p in pages), encoding='utf-8')
        self.root.joinpath('README.html').write_text('<!doctype html><meta charset="utf-8"><title>LeRobot 中文文档</title><h1>LeRobot 中文文档</h1><p>' + notice + '</p><ul>' + ''.join(f'<li><a href="{p["file"]}.html">{html.escape(p["title"])}</a></li>' for p in pages) + '</ul>', encoding='utf-8')
        self.root.joinpath('manifest.json').write_text(json.dumps({'source': self.base + self.prefix, 'downloaded_at': datetime.now(timezone.utc).isoformat(), 'pages': pages, 'errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'pages': len(pages), 'errors': errors, 'directory': str(self.root.resolve())}, ensure_ascii=False))


if __name__ == '__main__':
    DocumentationDownloader(Path(__file__).resolve().parents[1] / 'docs' / 'lerobot').run()
