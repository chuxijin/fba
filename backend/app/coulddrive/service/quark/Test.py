from api import QuarkApi

async def main():
    quark_api = QuarkApi(cookies="_UP_A4A_11_=wb96810d260d432e83d1b2c8a3e977be; b-user-id=7ff63f31-2b65-851c-d9be-d276cd1e0ad7; CwsSessionId=fd894104-cc70-49ec-8ec4-8aa2dc856fec; __sdid=AAQsNkUtCLQn+4dbsUTCeMJUbLc2JhiY3oXyfK8fYVLQrEzE3/lbj3jt+WiNDxO8yWI=; _UP_D_=pc; __pus=04a13058abec9e60af4c195b05cfbdc0AAQLm9Pm3KWoPotLB4MUJYGoNjrwp8rIKmecDxif1uUc8CvBMe9gVh+f2xenoi7lTGrY1JiJ5k3DotzrK6Krfb0L; __kp=272ca2d0-3229-11f0-8cd9-2d06f5f43866; __kps=AAQ5+b4SHbBzKU/bBaUMq4AR; __ktd=//1G6o0/l4/1xKgFU0sslw==; __uid=AAQ5+b4SHbBzKU/bBaUMq4AR; isg=BLi4ihR3JDzNukZfDcj1p_1tiWZKIRyrVJ0tc_IpvfOmDVr3mjDEO2hhwQW9WNSD; __puus=4c1e464381b86f992091029f84236289AASieUQDlcEUumFL5f8oiNmYiJPE6YvD+LzpJIotj4RfDMJo8u6J89LS8iN+KkHwDEaUFQBbrlmg7cxnud2Vbt8ShhVaspJZlBnUc/SZ1VKlTYIOSjBDwyxJGa8iXAoFKODf4s+zPmKaoIUi/ZVShmAn66xDxg9cvumKO92QJhNn9KGMPIIu4sYkn0fcRlo/E69fv3GhgFBE3KJPXq5ua4Wj")
    result = await quark_api.list("2e87c2631f394da98896d60a6e4a8ec7")
    print(result)

   # 运行异步主函数
import asyncio
asyncio.run(main())