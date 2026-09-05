#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest
from backend.app.media_studio.core.parsers.base import BaseMediaParser
from backend.app.media_studio.core.parsers.douyin import DouyinParser
from backend.app.media_studio.core.parsers.xhs import XHSParser
from backend.app.media_studio.schema.media import MediaParseParam
from backend.app.media_studio.service.media_studio_service import media_studio_service
from backend.common.exception.errors import RequestError


def test_extract_url_from_complex_text():
    # 模拟常见的抖音分享文案
    dy_text = (
        "7.92 复制打开抖音，看看【小明的作品】这一幕真的太震撼了！ "
        "https://v.douyin.com/iAN9abcd/ 08/11 l@N.rT :7pm"
    )
    url = BaseMediaParser.extract_url(dy_text)
    assert url == "https://v.douyin.com/iAN9abcd/"

    # 模拟常见的小红书分享文案
    xhs_text = (
        "小红书精选：周末去哪儿玩？这个地方太美了吧！ "
        "http://xhslink.com/a/XyZ123 复制整段进入小红书App"
    )
    url_xhs = BaseMediaParser.extract_url(xhs_text)
    assert url_xhs == "http://xhslink.com/a/XyZ123"

    # 无链接输入应抛出 RequestError
    with pytest.raises(RequestError):
        BaseMediaParser.extract_url("一段完全没有包含任何链接的纯文本内容")


def test_douyin_video_watermark_removal_logic():
    parser = DouyinParser()
    mock_detail = {
        "desc": "震撼人心的风景大片 #旅行 #摄影",
        "aweme_type": 4,
        "video": {
            "play_addr": {
                "url_list": [
                    "https://aweme.snssdk.com/aweme/v1/playwm/?video_id=v0200fg10000abcdefg&ratio=720p"
                ]
            },
            "cover": {
                "url_list": ["https://p3.douyinpic.com/cover123.jpg"]
            }
        },
        "author": {
            "nickname": "摄影师阿强",
            "sec_uid": "MS4wLjABAAAA...",
            "avatar_thumb": {"url_list": ["https://p3.douyinpic.com/avatar123.jpg"]}
        },
        "statistics": {
            "digg_count": 12000,
            "comment_count": 500,
            "collect_count": 3000,
            "share_count": 120
        }
    }
    res = parser._format_response(mock_detail, raw_url="https://www.douyin.com/video/123456")
    assert res.platform == "douyin"
    assert res.media_type == "video"
    assert res.video_url is not None
    # 必须去水印（playwm 替换为 play）
    assert "playwm" not in res.video_url
    assert "play/?video_id=" in res.video_url
    assert "旅行" in res.tags
    assert res.author.name == "摄影师阿强"
    assert res.stats.like_count == 12000


def test_douyin_images_extraction():
    parser = DouyinParser()
    mock_detail = {
        "desc": "每日穿搭图集分享",
        "aweme_type": 68,
        "images": [
            {"url_list": ["https://p3.douyinpic.com/img1.jpg", "https://p9.douyinpic.com/img1.jpg"]},
            {"url_list": ["https://p3.douyinpic.com/img2.jpg"]}
        ],
        "author": {"nickname": "穿搭博主"},
        "statistics": {"digg_count": 888}
    }
    res = parser._format_response(mock_detail, raw_url="https://www.douyin.com/note/123456")
    assert res.platform == "douyin"
    assert res.media_type == "image"
    assert len(res.images) == 2
    assert res.images[0] == "https://p3.douyinpic.com/img1.jpg"
    assert res.cover_url == "https://p3.douyinpic.com/img1.jpg"
    assert res.video_url is None


def test_xhs_clean_image_url():
    parser = XHSParser()
    raw_url_with_watermark = "https://sns-webpic-qc.xhscdn.com/20240101/abcd1234!nd_dft_wl_webp_3"
    cleaned = parser._clean_image_url(raw_url_with_watermark)
    assert cleaned == "https://sns-webpic-qc.xhscdn.com/20240101/abcd1234"

    raw_url_with_query = "https://sns-webpic-qc.xhscdn.com/20240101/abcd1234?imageView2/2/w/format/jpg"
    cleaned_query = parser._clean_image_url(raw_url_with_query)
    assert cleaned_query == "https://sns-webpic-qc.xhscdn.com/20240101/abcd1234"


def test_xhs_note_formatting():
    parser = XHSParser()
    mock_note = {
        "title": "爆款小红书笔记标题",
        "desc": "今天推荐这套超好看的装修设计方案 #室内设计 #家装灵感",
        "type": "normal",
        "imageList": [
            {"urlDefault": "https://sns-webpic-qc.xhscdn.com/2024/pic1!nd_dft_wl_webp_3"},
            {"urlDefault": "https://sns-webpic-qc.xhscdn.com/2024/pic2!nd_dft_wl_webp_3"}
        ],
        "user": {
            "nickname": "设计师小陈",
            "userId": "user_998877",
            "avatar": "https://sns-avatar-qc.xhscdn.com/avatar.jpg"
        },
        "tagList": [{"name": "室内设计"}, {"name": "家装灵感"}],
        "interactInfo": {
            "likedCount": 5420,
            "collectedCount": 3210,
            "commentCount": 180,
            "shareCount": 95
        }
    }
    res = parser._format_response(mock_note, raw_url="https://www.xiaohongshu.com/explore/654321")
    assert res.platform == "xhs"
    assert res.media_type == "image"
    assert res.title == "爆款小红书笔记标题"
    assert len(res.images) == 2
    assert res.images[0] == "https://sns-webpic-qc.xhscdn.com/2024/pic1"
    assert res.cover_url == "https://sns-webpic-qc.xhscdn.com/2024/pic1"
    assert res.author.name == "设计师小陈"
    assert res.stats.collect_count == 3210


@pytest.mark.asyncio
async def test_service_unsupported_platform():
    with pytest.raises(RequestError) as exc_info:
        await media_studio_service.parse_media(
            MediaParseParam(url_or_text="https://www.bilibili.com/video/BV1xx411c7mD")
        )
    assert "暂不支持该平台链接" in str(exc_info.value.msg)