import re
import sys

def read_multiline_input():
    """
    读取多行输入，直到遇到空行（直接按回车）结束
    """
    print("请输入或粘贴 HTML 内容（输入完成后多按一次回车结束）：")
    print("-" * 60)
    
    lines = []
    while True:
        try:
            line = input()
            if line == "":  # 检测到空行，结束输入
                break
            lines.append(line)
        except EOFError:  # 兼容 Ctrl+D/Ctrl+Z 结束
            break
        except KeyboardInterrupt:
            print("\n\n操作已取消")
            sys.exit()
    
    return '\n'.join(lines)

def process_news_html(html_content):
    """
    处理新闻联播HTML内容：
    1. 去除 \r\n，统一为 \n
    2. 提取 <strong> 和 <mark> 标签内容（保留标签）
    """
    # 统一换行符
    cleaned_html = html_content.replace('\r\n', '\n').replace('\r', '\n')
    
    # 提取 <strong> 和 <mark> 标签（支持跨行内容）
    pattern = r'<(strong|mark)[^>]*>.*?</\1>'
    
    main_content_lines = []
    for match in re.finditer(pattern, cleaned_html, re.DOTALL):
        line = match.group(0)
        # 清理标签内的多余空白，但保留标签结构
        line = re.sub(r'>\s+', '>', line)
        line = re.sub(r'\s+<', '<', line)
        line = re.sub(r'\s+', ' ', line)
        main_content_lines.append(line.strip())
    
    main_content = '\n'.join(main_content_lines)
    
    return cleaned_html, main_content

def main():
    # 读取输入
    input_text = read_multiline_input()
    
    if not input_text.strip():
        print("\n错误：未检测到输入内容")
        return
    
    # 处理
    full_text, summary = process_news_html(input_text)
    
    # 输出结果
    print("\n" + "=" * 70)
    print("【一、去除 \\r\\n 后的完整原文】")
    print("=" * 70)
    print(full_text)
    
    print("\n" + "=" * 70)
    print("【二、提取的主要内容（<strong> 和 <mark> 标签）】")
    print("=" * 70)
    if summary:
        print(summary)
    else:
        print("（未找到 <strong> 或 <mark> 标签）")
    
    print("\n" + "=" * 70)
    print("处理完成")
    print("=" * 70)

if __name__ == "__main__":
    main()