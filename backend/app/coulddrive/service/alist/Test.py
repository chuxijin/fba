from api import AlistApi

async def main():
    alist_api = AlistApi(token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImFkbWluIiwicHdkX3RzIjoxNzQwOTY2MDMwLCJleHAiOjE3NDgxMzgyNzEsIm5iZiI6MTc0Nzk2NTQ3MSwiaWF0IjoxNzQ3OTY1NDcxfQ.Lw_u59E3Vmo5m6mNoW987Ax37KwNbRVMk0EvSJj_-Ho")
    result = await alist_api.list("/")
    print(result)

   # 运行异步主函数
import asyncio
asyncio.run(main())