import asyncio
import os

import httpx


async def test_llamaparse_api():
    api_key = os.environ.get("LLAMA_CLOUD_API_KEY", "llx-lh7d6DvCeMcjsh1TWAXVsCS0EERyD8a5nD6nIXAgXdgXpQ8C")
    base_url = "https://api.cloud.llamaindex.ai/api/parsing"
    
    file_path = r"C:\Users\19396\Desktop\简历.pdf"
    
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=120) as client:
        # 1. Upload
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {
                "language": "ch_sim",
                "premium_mode": "true",
                "parse_images": "true"
            }
            print("上传...")
            upload_res = await client.post(f"{base_url}/upload", headers=headers, files=files, data=data)
            if upload_res.status_code != 200:
                print(f"上传失败: {upload_res.status_code}")
                print(upload_res.text)
            upload_res.raise_for_status()
            job_id = upload_res.json()["id"]
        
        print(f"作业 ID: {job_id}")
        
        # 2. Wait
        while True:
            await asyncio.sleep(3)
            status_res = await client.get(f"{base_url}/job/{job_id}", headers=headers)
            status = status_res.json()["status"]
            print(f"状态: {status}")
            if status == "SUCCESS":
                break
            elif status == "ERROR":
                print(f"错误! {status_res.json()}")
                return
                
        # 3. Get Result
        # API 结构可能是 /job/{job_id}/result/markdown ?
        res = await client.get(f"{base_url}/job/{job_id}/result/markdown", headers=headers)
        if res.status_code == 200:
            print("直接返回 Markdown 成功")
            md_content = res.json().get("markdown", "")
            print(md_content[:200])

        
if __name__ == "__main__":
    asyncio.run(test_llamaparse_api())
