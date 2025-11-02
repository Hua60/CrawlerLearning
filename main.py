import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime
import time
import re
from urllib.parse import urljoin, urlparse, quote
import json
from collections import deque
import random

# Selenium相关导入
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("警告: Selenium未安装，将使用基础爬取模式")

class ShanxiTourismNewsCrawler:
    """山西文旅新闻全网自动化爬虫 - 增强版"""

    def __init__(self, use_selenium=True):
        # 多个User-Agent轮换
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        ]

        self.news_data = []
        self.visited_urls = set()
        self.target_start_date = datetime(2025, 10, 1)
        self.target_end_date = datetime(2025, 10, 10)

        # 山西文旅相关关键词
        self.keywords = ['山西文旅', '山西旅游', '山西景区', '平遥古城', '五台山',
                        '云冈石窟', '壶口瀑布', '晋祠', '山西文化', '山西国庆']

        # 创建Session
        self.session = requests.Session()

        # 设置重试策略
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Selenium配置
        self.use_selenium = use_selenium and SELENIUM_AVAILABLE
        self.driver = None

    def init_selenium(self):
        """初始化Selenium浏览器"""
        if not SELENIUM_AVAILABLE or not self.use_selenium:
            return False

        try:
            print("  → 正在启动浏览器驱动...")
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument(f'user-agent={random.choice(self.user_agents)}')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            # 设置页面加载超时
            self.driver.set_page_load_timeout(30)

            print("  ✓ 浏览器驱动启动成功")
            return True
        except Exception as e:
            print(f"  ✗ 浏览器驱动启动失败: {str(e)[:100]}")
            print("  → 将使用基础爬取模式")
            self.use_selenium = False
            return False

    def close_selenium(self):
        """关闭Selenium浏览器"""
        if self.driver:
            try:
                self.driver.quit()
                print("  ✓ 浏览器驱动已关闭")
            except:
                pass

    def get_random_headers(self):
        """获取随机请求��"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
        }

    def random_delay(self, min_seconds=1, max_seconds=3):
        """随机延迟"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def safe_request(self, url, method='GET', max_retries=3, **kwargs):
        """安全的HTTP请求"""
        for attempt in range(max_retries):
            try:
                headers = kwargs.get('headers', self.get_random_headers())
                kwargs['headers'] = headers

                if 'timeout' not in kwargs:
                    kwargs['timeout'] = 15

                if method.upper() == 'GET':
                    response = self.session.get(url, **kwargs)
                else:
                    response = self.session.post(url, **kwargs)

                if response.status_code == 200:
                    return response
                elif response.status_code == 403:
                    print(f"  ⚠ 访问被拒绝(403)，尝试切换策略...")
                    self.random_delay(2, 4)
                elif response.status_code == 429:
                    print(f"  ⚠ 请求过于频繁(429)，等待后重试...")
                    self.random_delay(5, 10)
                else:
                    print(f"  ⚠ HTTP {response.status_code}")

            except requests.exceptions.Timeout:
                print(f"  ⚠ 请求超时，重试中... ({attempt + 1}/{max_retries})")
                self.random_delay(2, 4)
            except requests.exceptions.ConnectionError:
                print(f"  ⚠ 连接错误，重试中... ({attempt + 1}/{max_retries})")
                self.random_delay(2, 4)
            except Exception as e:
                print(f"  ⚠ 请求异常: {str(e)[:50]}")
                if attempt < max_retries - 1:
                    self.random_delay(2, 4)

        return None

    def selenium_get_page(self, url):
        """使用Selenium获取页面"""
        if not self.driver:
            if not self.init_selenium():
                return None

        try:
            self.driver.get(url)
            self.random_delay(2, 4)  # 等待页面加载
            return self.driver.page_source
        except Exception as e:
            print(f"  ⚠ Selenium获取页面失败: {str(e)[:50]}")
            return None

    def search_news_apis(self):
        """使用新闻API搜索（更可靠的方法）"""
        print("\n正在通过新闻API搜索...")

        # 搜狗微信搜索（公开API）
        try:
            print("  → 搜狗微信搜索")
            for keyword in self.keywords[:8]:  # 增加到8个关键词
                search_url = f"https://weixin.sogou.com/weixin?type=2&query={quote(keyword + ' 10月')}"

                if self.use_selenium:
                    html = self.selenium_get_page(search_url)
                else:
                    response = self.safe_request(search_url)
                    html = response.text if response else None

                if html:
                    soup = BeautifulSoup(html, 'html.parser')
                    articles = soup.find_all('div', class_='txt-box')

                    count = 0
                    for article in articles[:50]:  # 增加到50条
                        try:
                            title_tag = article.find('h3')
                            if not title_tag:
                                continue

                            title = title_tag.get_text(strip=True)
                            link_tag = title_tag.find('a')
                            link = link_tag.get('href', '') if link_tag else ''

                            # 修复：确保链接是完整URL
                            if link:
                                if link.startswith('/'):
                                    link = 'https://weixin.sogou.com' + link
                                elif not link.startswith('http'):
                                    link = 'https://weixin.sogou.com/' + link

                            if link and link not in self.visited_urls:
                                self.visited_urls.add(link)

                                # 提取摘要
                                summary_tag = article.find('p', class_='txt-info')
                                content = summary_tag.get_text(strip=True) if summary_tag else ''

                                date_str = self.extract_date_from_text(title + content)

                                self.news_data.append({
                                    '标题': title,
                                    '日期': date_str or '2025-10',
                                    '链接': link,
                                    '内容': content[:500] if content else '未获取到内容',
                                    '来源': '微信公众号'
                                })
                                print(f"    ✓ {title[:40]}...")
                                count += 1
                        except:
                            continue

                    print(f"    采集 {count} 条")
                    self.random_delay(3, 5)
        except Exception as e:
            print(f"  ✗ 微信搜索失败: {str(e)[:50]}")

    def crawl_government_sites(self):
        """爬取山西政府官方网站"""
        print("\n正在爬取政府官方网站...")

        sites = [
            {
                'name': '山西省文化和旅游厅',
                'url': 'http://wlt.shanxi.gov.cn/',
                'list_selector': 'a',
                'encoding': 'utf-8'
            },
            {
                'name': '太原市文化和旅游局',
                'url': 'http://wlj.taiyuan.gov.cn/',
                'list_selector': 'a',
                'encoding': 'utf-8'
            }
        ]

        for site in sites:
            try:
                print(f"  → {site['name']}")

                response = self.safe_request(site['url'])
                if not response:
                    continue

                response.encoding = site['encoding']
                soup = BeautifulSoup(response.text, 'html.parser')

                links = soup.find_all('a', href=True)
                count = 0

                for link in links[:100]:  # 增加到100个链接
                    if count >= 50:  # 增加到50条数据
                        break

                    try:
                        title = link.get_text(strip=True)
                        href = urljoin(site['url'], link['href'])

                        # 检查关键词
                        if len(title) < 10:
                            continue

                        if any(kw in title for kw in ['旅游', '文旅', '景区', '国庆', '假期', '10月', '十月']):
                            if href not in self.visited_urls:
                                self.visited_urls.add(href)

                                self.random_delay(1, 2)
                                content = self.extract_content_from_url(href)

                                date_str = self.extract_date_from_text(title + content)

                                self.news_data.append({
                                    '标题': title,
                                    '日期': date_str or '2025-10',
                                    '链接': href,
                                    '内容': content[:500] if content else '未获取到内容',
                                    '来源': site['name']
                                })
                                print(f"    ✓ {title[:40]}...")
                                count += 1
                    except:
                        continue

                print(f"    采集 {count} 条")
                self.random_delay(2, 4)

            except Exception as e:
                print(f"  ✗ {site['name']} 爬取失败: {str(e)[:50]}")

    def search_baidu(self, keyword, pages=3):
        """使用百度搜索"""
        print(f"\n正在百度搜索: {keyword}")

        for page in range(pages):
            try:
                search_url = f"https://www.baidu.com/s?wd={quote(keyword + ' 2025年10月 新闻')}&pn={page * 10}&rn=10"

                if self.use_selenium:
                    html = self.selenium_get_page(search_url)
                else:
                    response = self.safe_request(search_url)
                    html = response.text if response else None

                if not html:
                    print(f"  ✗ 第{page+1}页获取失败")
                    continue

                soup = BeautifulSoup(html, 'html.parser')
                results = soup.find_all('div', class_=re.compile(r'result.*|c-container'))

                if not results:
                    results = soup.find_all('div', attrs={'tpl': True})

                found_count = 0
                for result in results[:10]:
                    try:
                        title_tag = result.find('h3') or result.find('a')
                        if not title_tag:
                            continue

                        link_tag = title_tag.find('a') if title_tag.name == 'h3' else title_tag
                        if not link_tag:
                            continue

                        title = title_tag.get_text(strip=True)
                        link = link_tag.get('href', '')

                        if not link or 'baidu.com' in link or link in self.visited_urls:
                            continue

                        if any(kw in title for kw in ['10月', '国庆', '十月', '文旅', '旅游', '景区', '山西']):
                            self.visited_urls.add(link)
                            self.random_delay(1, 2)

                            content = self.extract_content_from_url(link)
                            date_str = self.extract_date_from_text(title + content)

                            self.news_data.append({
                                '标题': title,
                                '日期': date_str or '2025-10',
                                '链接': link,
                                '内容': content[:500] if content else '未获取到内容',
                                '来源': '百度搜索'
                            })
                            print(f"  ✓ {title[:50]}...")
                            found_count += 1

                    except Exception as e:
                        continue

                print(f"  → 第{page+1}页采集 {found_count} 条")
                self.random_delay(3, 5)

            except Exception as e:
                print(f"  ✗ 搜索失败: {str(e)[:50]}")

    def crawl_news_sites(self):
        """爬��主流新闻网站"""
        print("\n正在爬取主流新闻网站...")

        # 使用API或RSS源
        self.crawl_xinhua_rss()
        self.crawl_people_shanxi()
        self.crawl_163_news()

    def crawl_xinhua_rss(self):
        """爬取新华网RSS"""
        print("\n  → 新华网山西")
        try:
            urls = [
                'http://www.sx.xinhuanet.com/',
                'http://www.news.cn/travel/',
            ]

            for url in urls:
                response = self.safe_request(url)
                if not response:
                    continue

                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.find_all('a', href=True)

                count = 0
                for link in links[:100]:  # 增加到100个链接
                    if count >= 30:  # 增加到30条
                        break

                    try:
                        title = link.get_text(strip=True)
                        href = urljoin(url, link['href'])

                        if len(title) < 10:
                            continue

                        if any(kw in title for kw in ['山西', '旅游', '文旅', '景区', '国庆', '10月']):
                            if href not in self.visited_urls:
                                self.visited_urls.add(href)
                                self.random_delay(1, 2)

                                content = self.extract_content_from_url(href)
                                date_str = self.extract_date_from_text(content)

                                self.news_data.append({
                                    '标题': title,
                                    '日期': date_str or '2025-10',
                                    '链接': href,
                                    '内容': content[:500] if content else '未获取到内容',
                                    '来源': '新华网'
                                })
                                print(f"    ✓ {title[:40]}...")
                                count += 1
                    except:
                        continue

                self.random_delay(2, 3)

        except Exception as e:
            print(f"    ✗ 失败: {str(e)[:50]}")

    def crawl_people_shanxi(self):
        """爬取人民网山西"""
        print("\n  → 人民网山西")
        try:
            url = 'http://sx.people.com.cn/'
            response = self.safe_request(url)

            if response:
                response.encoding = 'gb2312'
                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.find_all('a', href=True)

                count = 0
                for link in links[:100]:  # 增加到100个链接
                    if count >= 30:  # 增加到30条
                        break

                    try:
                        title = link.get_text(strip=True)
                        href = urljoin(url, link['href'])

                        if len(title) > 10 and any(kw in title for kw in ['旅游', '文旅', '景区', '国庆', '山西']):
                            if href not in self.visited_urls:
                                self.visited_urls.add(href)
                                self.random_delay(1, 2)

                                content = self.extract_content_from_url(href)
                                date_str = self.extract_date_from_text(content)

                                self.news_data.append({
                                    '标题': title,
                                    '日期': date_str or '2025-10',
                                    '链接': href,
                                    '内容': content[:500] if content else '未获取到内容',
                                    '来源': '人民网山西'
                                })
                                print(f"    ✓ {title[:40]}...")
                                count += 1
                    except:
                        continue

        except Exception as e:
            print(f"    ✗ 失败: {str(e)[:50]}")

    def crawl_163_news(self):
        """爬取网易新闻"""
        print("\n  → 网易新闻")
        try:
            url = 'https://news.163.com/travel/'
            response = self.safe_request(url)

            if response:
                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.find_all('a', href=True)

                count = 0
                for link in links[:100]:  # 增加到100个链接
                    if count >= 30:  # 增加到30条
                        break

                    try:
                        title = link.get_text(strip=True)
                        href = link['href']

                        if len(title) > 10 and any(kw in title for kw in ['山西', '旅游', '景区']):
                            if href not in self.visited_urls:
                                self.visited_urls.add(href)
                                self.random_delay(1, 2)

                                content = self.extract_content_from_url(href)
                                date_str = self.extract_date_from_text(content)

                                self.news_data.append({
                                    '标题': title,
                                    '日期': date_str or '2025-10',
                                    '链接': href,
                                    '内容': content[:500] if content else '未获取到内容',
                                    '来源': '网易新闻'
                                })
                                print(f"    ✓ {title[:40]}...")
                                count += 1
                    except:
                        continue

        except Exception as e:
            print(f"    ✗ 失败: {str(e)[:50]}")

    def extract_date_from_text(self, text):
        """从文本中提取日期"""
        if not text:
            return ''

        patterns = [
            r'2025[-./年]\s*10\s*[-./月]\s*([1-9]|10)\s*[日号]?',
            r'10\s*[-./月]\s*([1-9]|10)\s*[日号]',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                date_text = match.group(0)
                numbers = re.findall(r'\d+', date_text)
                if len(numbers) >= 2:
                    month = numbers[-2]
                    day = numbers[-1]
                    if int(month) == 10 and 1 <= int(day) <= 10:
                        return f'2025-10-{day.zfill(2)}'

        return ''

    def extract_content_from_url(self, url):
        """从URL提取内容"""
        try:
            response = self.safe_request(url)
            if not response:
                return "内容获取失败"

            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')

            for script in soup(['script', 'style', 'iframe', 'nav', 'footer', 'header', 'aside']):
                script.decompose()

            content_selectors = [
                soup.find('div', class_=re.compile(r'.*content.*|.*article.*|.*detail.*|.*post.*', re.I)),
                soup.find('div', id=re.compile(r'.*content.*|.*article.*|.*main.*', re.I)),
                soup.find('article'),
            ]

            for selector in content_selectors:
                if selector:
                    content = selector.get_text(strip=True, separator='\n')
                    if len(content) > 100:
                        return content[:1000]

            body = soup.find('body')
            if body:
                content = body.get_text(strip=True, separator='\n')
                return content[:1000]

            return "内容获取失败"
        except Exception as e:
            return f"内容获取错误"

    def save_to_csv(self, filename='山西文旅新闻_全网爬取_10月1日至10日.csv'):
        """保存数据到CSV"""
        if not self.news_data:
            print("\n⚠ 警告: 没有采集到任何数据！")
            print("可能的原因:")
            print("  1. 网络连接问题")
            print("  2. 网站反爬虫限制")
            print("  3. 关键词匹配失败")
            print("\n建议:")
            print("  1. 检查网络连接")
            print("  2. 安装Selenium: pip install selenium webdriver-manager")
            print("  3. 调整关键词和时间范围")
            return

        print(f"\n正在保存到 {filename}...")

        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            fieldnames = ['标题', '日期', '链接', '内容', '来源']
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            writer.writeheader()
            for news in self.news_data:
                writer.writerow(news)

        print(f"✓ 成功保存 {len(self.news_data)} 条新闻到 {filename}")

    def run(self):
        """运行爬虫"""
        print("=" * 70)
        print("山西文旅新闻全网自动化爬虫 - 增强版（大数据模式）")
        print("=" * 70)

        if SELENIUM_AVAILABLE:
            print("\n✓ Selenium可用 - 将使用浏览器模式")
        else:
            print("\n⚠ Selenium不可用 - 使用基础模式")
            print("  安装命令: pip install selenium webdriver-manager")

        print("\n爬取策略（最大化数据采集）:")
        print("  1. 政府官方网站 - 每站最多50条")
        print("  2. 主流新闻网站 - 每站最多30条")
        print("  3. 百度搜索 - 3个关键词 × 10页")
        print("  4. 微信公众号 - 8个关键词 × 50条")
        print("\n预估可采集数据量: 500+ 条")
        print("=" * 70)

        try:
            # 1. 政府网站（最可靠）
            print("\n【阶段1】政府官方网站")
            print("-" * 70)
            self.crawl_government_sites()

            # 2. 主流新闻网站
            print("\n【阶段2】主流新闻网站")
            print("-" * 70)
            self.crawl_news_sites()

            # 3. 搜索引擎 - 增加到10页，移除数据量限制
            print("\n【阶段3】搜索引擎深度爬取")
            print("-" * 70)
            for keyword in self.keywords[:3]:  # 增加到3个关键词
                self.search_baidu(keyword, pages=10)  # 增加到10页
                print(f"  当前已采集: {len(self.news_data)} 条")

            # 4. 微信公众号 - 移除数据量限制
            if self.use_selenium:
                print("\n【阶段4】微信公众号")
                print("-" * 70)
                self.search_news_apis()

        except KeyboardInterrupt:
            print("\n\n用户中断爬取...")
        except Exception as e:
            print(f"\n爬取过程出错: {str(e)}")
        finally:
            # 关闭浏览器
            self.close_selenium()

        # 保存数据
        print("\n【阶段5】保存数据")
        print("-" * 70)
        self.save_to_csv()

        # 统计
        print("\n" + "=" * 70)
        print("爬取完成！统计信息:")
        print("=" * 70)
        print(f"总采集新闻数: {len(self.news_data)} 条")
        print(f"已访问URL数: {len(self.visited_urls)} 个")

        if self.news_data:
            sources = {}
            for news in self.news_data:
                source = news['来源']
                sources[source] = sources.get(source, 0) + 1

            print("\n来源分布:")
            for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
                print(f"  • {source}: {count} 条")

            print("\n数据已保存至: 山西文旅新闻_全网爬取_10月1日至10日.csv")

        print("=" * 70)


if __name__ == '__main__':
    crawler = ShanxiTourismNewsCrawler(use_selenium=True)
    crawler.run()
