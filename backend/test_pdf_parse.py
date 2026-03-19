import asyncio
import os
from llama_parse import LlamaParse
from llama_index.core.schema import Document

os.environ["LLAMA_CLOUD_API_KEY"] = "llx-lh7d6DvCeMcjsh1TWAXVsCS0EERyD8a5nD6nIXAgXdgXpQ8C"

async def main():
    pdf_path = r"C:\Users\19396\Desktop\简历.pdf"
    
    # 设定图片要保存的本地文件夹
    image_download_dir = "./parsed_images"
    os.makedirs(image_download_dir, exist_ok=True)

    print(f"🚀 开始极致解析并提取图片: {pdf_path}")
    print("使用了 Agentic 模式，耗时较长，请耐心等待...")

    parser = LlamaParse(
        result_type="markdown",       # 结果转为 Markdown
        premium_mode=True,            # 开启高级大模型解析（支持公式）
        language="zh",                # 中文为主
        
        # 👇 抠图的核心配置 👇
        parse_images=True,            # 决定是否把 PDF 里的图抠出来
        images_dir=image_download_dir # 图片存到哪里？并且 Markdown 里的链接会自动指向这里
    )

    try:
        # 这一步会自动跑到云端解析，并把图片一一拉回来存在 parsed_images 文件夹！
        documents = await parser.aload_data(pdf_path)

        full_md = "\n\n".join([doc.text for doc in documents])
        
        output_md_path = "./test_parsed_with_images.md"
        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write(full_md)

        print("\n✅ 解析并抠图成功！")
        print(f"👉 带图 Markdown 已保存至: {output_md_path}")
        print(f"👉 提取出来的图片已保存至: {image_download_dir} 文件夹下")

    except Exception as e:
        print(f"❌ 解析失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
