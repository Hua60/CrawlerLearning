import csv

# 读取CSV文件
with open('山西文旅新闻_全网爬取_10月1日至10日.csv', 'r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"CSV文件总共有 {len(rows)} 条有效数据\n")

print("=" * 100)
print("检查前20条新闻的链接:")
print("=" * 100)

for i, row in enumerate(rows[:20], start=1):
    title = row.get('标题', 'N/A')
    link = row.get('链接', 'N/A')
    source = row.get('来源', 'N/A')

    print(f"\n{i}. 【{source}】")
    print(f"   标题: {title[:60]}...")
    print(f"   链接: {link[:120]}")

    # 检查链接是否有效
    if link.startswith('http'):
        print(f"   ✓ 链接格式正常")
    else:
        print(f"   ✗ 链接格式异常！")

# 统计微信公众号的链接
print("\n" + "=" * 100)
print("微信公众号链接分析:")
print("=" * 100)

weixin_rows = [row for row in rows if row.get('来源') == '微信公众号']
print(f"微信公众号新闻总数: {len(weixin_rows)}")

for i, row in enumerate(weixin_rows[:10], start=1):
    link = row.get('链接', 'N/A')
    title = row.get('标题', 'N/A')
    print(f"\n{i}. {title[:50]}...")
    print(f"   链接: {link}")

    # 检查链接类型
    if 'weixin.sogou.com' in link:
        print(f"   ⚠ 这是搜狗微信的跳转链接，不是真实的微信文章链接！")
    elif 'mp.weixin.qq.com' in link:
        print(f"   ✓ 这是真实的微信公众号文章链接")
    else:
        print(f"   ✗ 链接格式异常")

