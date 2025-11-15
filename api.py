import json
import aiohttp
from astrbot import logger

# 偷来的key
PARAMS = "D33zyir4L/58v1qGPcIPjSee79KCzxBIBy507IYDB8EL7jEnp41aDIqpHBhowfQ6iT1Xoka8jD+0p44nRKNKUA0dv+n5RWPOO57dZLVrd+T1J/sNrTdzUhdHhoKRIgegVcXYjYu+CshdtCBe6WEJozBRlaHyLeJtGrABfMOEb4PqgI3h/uELC82S05NtewlbLZ3TOR/TIIhNV6hVTtqHDVHjkekrvEmJzT5pk1UY6r0="
ENC_SEC_KEY = "45c8bcb07e69c6b545d3045559bd300db897509b8720ee2b45a72bf2d3b216ddc77fb10daec4ca54b466f2da1ffac1e67e245fea9d842589dc402b92b262d3495b12165a721aed880bf09a0a99ff94c959d04e49085dc21c78bbbe8e3331827c0ef0035519e89f097511065643120cbc478f9c0af96400ba4649265781fc9079"


class NetEaseMusicAPI:
    """
    网易云音乐API
    """

    def __init__(self):
        self.header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/55.0.2883.87 UBrowser/6.2.4098.3 Safari/537.36"
        }
        self.headers = {"referer": "http://music.163.com"}
        self.cookies = {"appver": "2.0.2"}
        self.session = aiohttp.ClientSession()

    async def _request(
        self,
        url: str,
        data: dict = {},
        method: str = "GET",
    ):
        """统一请求接口"""
        if method.upper() == "POST":
            async with self.session.post(
                url, headers=self.header, cookies=self.cookies, data=data
            ) as response:
                if response.headers.get("Content-Type") == "application/json":
                    return await response.json()
                else:
                    return json.loads(await response.text())

        elif method.upper() == "GET":
            async with self.session.get(
                url, headers=self.headers, cookies=self.cookies
            ) as response:
                return await response.json()
        else:
            raise ValueError("不支持的请求方式")

    async def fetch_data(self, keyword: str, limit=5) -> list[dict]:
        """搜索歌曲"""
        url = "http://music.163.com/api/search/get/web"
        data = {"s": keyword, "limit": limit, "type": 1, "offset": 0}
        result = await self._request(url, data=data, method="POST")
        return [
            {
                "id": song["id"],
                "name": song["name"],
                "artists": "、".join(artist["name"] for artist in song["artists"]),
                "duration": song["duration"],
            }
            for song in result["result"]["songs"][:limit]
        ]

    async def fetch_comments(self, song_id: int):
        """获取热评"""
        url = f"https://music.163.com/weapi/v1/resource/hotcomments/R_SO_4_{song_id}?csrf_token="
        data = {
            "params": PARAMS,
            "encSecKey": ENC_SEC_KEY,
        }
        result = await self._request(url, data=data, method="POST")
        return result.get("hotComments", [])

    async def fetch_lyrics(self, song_id):
        """获取歌词"""
        url = f"https://netease-music.api.harisfox.com/lyric?id={song_id}"
        result = await self._request(url)
        return result.get("lrc", {}).get("lyric", "歌词未找到")

    async def fetch_extra(self, song_id: str | int) -> dict[str, str]:
        """
        获取额外信息
        """
        url = f"https://www.hhlqilongzhu.cn/api/dg_wyymusic.php?id={song_id}&br=7&type=json"
        result = await self._request(url)
        return {
            "title": result.get("title"),
            "author": result.get("singer"),
            "cover_url": result.get("cover"),
            "audio_url": result.get("music_url"),
        }
    async def close(self):
        await self.session.close()


class NetEaseMusicAPINodeJs:
    """
    网易云音乐API NodeJs版本
    """

    def __init__(self, base_url: str):
        # http://netease_cloud_music_api:{port}/
        self.base_url = base_url.rstrip("/")
        self.session = aiohttp.ClientSession(base_url=self.base_url)
        self._post_headers = {"Content-Type": "application/json"}
        self._last_error_message: str | None = None

    @property
    def last_error_message(self) -> str | None:
        return self._last_error_message

    async def _request(
        self,
        url: str,
        data: dict | None = None,
        method: str = "GET",
    ):
        method = method.upper()
        self._last_error_message = None
        payload = data or {}
        request_kwargs: dict[str, object] = {}
        headers: dict[str, str] = {}

        if method == "POST":
            headers.update(self._post_headers)
            request_kwargs["json"] = payload
        elif method == "GET" and payload:
            request_kwargs["params"] = payload

        if headers:
            request_kwargs["headers"] = headers

        if payload:
            logger.debug(
                "NetEase Node API request | %s %s | payload=%s",
                method,
                url,
                payload,
            )
        else:
            logger.debug("NetEase Node API request | %s %s", method, url)

        try:
            async with self.session.request(method, url, **request_kwargs) as response:
                status = response.status
                text = await response.text()
                body_preview = text[:500].strip()
                logger.debug(
                    "NetEase Node API response | %s %s | status=%s | body=%s",
                    method,
                    url,
                    status,
                    body_preview,
                )

                if status >= 400:
                    message = f"网易云音乐节点 API 请求失败 (HTTP {status})"
                    logger.error("%s，响应内容：%s", message, body_preview)
                    self._last_error_message = message
                    return {
                        "success": False,
                        "message": message,
                        "status": status,
                        "raw": text,
                    }

                if not body_preview:
                    message = "网易云音乐节点 API 返回空响应"
                    logger.error(message)
                    self._last_error_message = message
                    return {
                        "success": False,
                        "message": message,
                        "status": status,
                    }

                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    message = "网易云音乐节点 API 返回无法解析的内容"
                    logger.error("%s：%s", message, body_preview)
                    self._last_error_message = message
                    return {
                        "success": False,
                        "message": message,
                        "status": status,
                        "raw": text,
                    }

                if (
                    isinstance(parsed, dict)
                    and parsed.get("code") is not None
                    and parsed.get("code") != 200
                ):
                    message = parsed.get("msg") or parsed.get("message") or (
                        f"网易云音乐节点 API 返回错误码：{parsed.get('code')}"
                    )
                    logger.error("%s，响应内容：%s", message, body_preview)
                    self._last_error_message = message
                    parsed["success"] = False
                    parsed["message"] = message
                    parsed["status"] = parsed.get("code")
                return parsed
        except aiohttp.ClientError as exc:
            message = f"网易云音乐节点 API 请求异常：{exc}"
            logger.error(message)
            self._last_error_message = message
            return {"success": False, "message": message}
        except Exception as exc:
            message = f"网易云音乐节点 API 未知错误：{exc}"
            logger.exception(message)
            self._last_error_message = message
            return {"success": False, "message": message}

    async def fetch_data(self, keyword: str, limit=5) -> list[dict] | None:
        """搜索歌曲"""
        url = "/search"
        data = {"keywords": keyword, "limit": limit, "type": 1, "offset": 0}

        result = await self._request(url, data=data, method="POST")
        if not isinstance(result, dict):
            message = "网易云音乐服务返回了无法解析的数据，请稍后再试~"
            logger.error("搜索歌曲失败：响应格式异常")
            self._last_error_message = message
            return None
        if result.get("success") is False:
            message = result.get("message") or "网易云音乐服务暂时不可用，请稍后再试~"
            logger.error("搜索歌曲失败：%s", message)
            self._last_error_message = message
            return None
        if result.get("code") is not None and result.get("code") != 200:
            raw_message = result.get("message") or result.get("msg") or (
                f"网易云音乐节点 API 返回错误码：{result.get('code')}"
            )
            message = f"网易云音乐服务暂时不可用：{raw_message}"
            logger.error("搜索歌曲失败：%s", raw_message)
            self._last_error_message = message
            return None

        result_block = result.get("result")
        if not isinstance(result_block, dict):
            message = "网易云音乐服务返回数据异常，请稍后再试~"
            logger.warning("搜索歌曲失败：响应缺少 result 字段")
            self._last_error_message = message
            return None

        songs = result_block.get("songs")
        if not isinstance(songs, list):
            message = "网易云音乐服务返回数据异常，请稍后再试~"
            logger.warning("搜索歌曲失败：songs 字段不是列表")
            self._last_error_message = message
            return None
        if not songs:
            logger.info("关键词 \"%s\" 未找到歌曲", keyword)
            self._last_error_message = None
            return []

        parsed_songs: list[dict] = []
        for song in songs[:limit]:
            if not isinstance(song, dict):
                continue
            song_id = song.get("id")
            if song_id is None:
                continue
            artists_field = song.get("artists") or []
            if isinstance(artists_field, list):
                artists = "、".join(
                    artist.get("name", "未知")
                    for artist in artists_field
                    if isinstance(artist, dict)
                )
            else:
                artists = str(artists_field)

            parsed_songs.append(
                {
                    "id": song_id,
                    "name": song.get("name", "未知"),
                    "artists": artists,
                    "duration": song.get("duration", 0),
                }
            )

        if not parsed_songs:
            logger.info("关键词 \"%s\" 未找到可用的歌曲数据", keyword)
            self._last_error_message = None
            return []

        self._last_error_message = None
        return parsed_songs

    async def fetch_comments(self, song_id: int):
        """获取热评"""
        url = "/comment/hot"
        data = {
            "id": song_id,
            "type": 0,
        }
        result = await self._request(url, data=data, method="POST")
        if not isinstance(result, dict):
            logger.error("获取热评失败：响应格式异常")
            return []
        if result.get("success") is False:
            logger.error("获取热评失败：%s", result.get("message", "未知错误"))
            return []
        if result.get("code") is not None and result.get("code") != 200:
            message = result.get("message") or result.get("msg") or (
                f"网易云音乐节点 API 返回错误码：{result.get('code')}"
            )
            logger.error("获取热评失败：%s", message)
            return []

        comments = result.get("hotComments")
        if not isinstance(comments, list):
            logger.info("歌曲 %s 没有热评或响应格式不正确", song_id)
            return []
        return comments

    async def fetch_lyrics(self, song_id):
        """获取歌词"""
        url = f"{self.base_url}/lyric?id={song_id}"
        result = await self._request(url)
        if not isinstance(result, dict):
            logger.error("获取歌词失败：响应格式异常")
            return "歌词未找到"
        if result.get("success") is False:
            logger.error("获取歌词失败：%s", result.get("message", "未知错误"))
            return "歌词未找到"
        if result.get("code") is not None and result.get("code") != 200:
            message = result.get("message") or result.get("msg") or (
                f"网易云音乐节点 API 返回错误码：{result.get('code')}"
            )
            logger.error("获取歌词失败：%s", message)
            return "歌词未找到"

        lyrics_block = result.get("lrc", {})
        if not isinstance(lyrics_block, dict):
            logger.info("歌曲 %s 未找到歌词", song_id)
            return "歌词未找到"

        lyric = lyrics_block.get("lyric")
        if not lyric:
            logger.info("歌曲 %s 未找到歌词", song_id)
            return "歌词未找到"
        return lyric

    async def fetch_extra(self, song_id: str | int) -> dict[str, str]:
        """
        获取额外信息
        """
        url = "/song/url"
        data = {"id": song_id}
        result = await self._request(url, data=data, method="POST")
        if not isinstance(result, dict):
            message = "网易云音乐服务返回了无法解析的数据，请稍后再试~"
            logger.error("获取歌曲链接失败：响应格式异常")
            self._last_error_message = message
            return {"audio_url": ""}
        if result.get("success") is False:
            message = result.get("message") or "网易云音乐服务暂时不可用，请稍后再试~"
            logger.error("获取歌曲链接失败：%s", message)
            self._last_error_message = message
            return {"audio_url": ""}
        if result.get("code") is not None and result.get("code") != 200:
            raw_message = result.get("message") or result.get("msg") or (
                f"网易云音乐节点 API 返回错误码：{result.get('code')}"
            )
            message = f"网易云音乐服务暂时不可用：{raw_message}"
            logger.error("获取歌曲链接失败：%s", raw_message)
            self._last_error_message = message
            return {"audio_url": ""}

        data_block = result.get("data")
        if not isinstance(data_block, list) or not data_block:
            message = "网易云音乐服务未返回播放链接，请稍后再试~"
            logger.info("歌曲 %s 未返回播放链接", song_id)
            self._last_error_message = message
            return {"audio_url": ""}

        first_item = data_block[0] if isinstance(data_block[0], dict) else {}
        audio_url = first_item.get("url", "") if isinstance(first_item, dict) else ""
        if not audio_url:
            message = "网易云音乐服务未返回播放链接，请稍后再试~"
            logger.info("歌曲 %s 未返回播放链接", song_id)
            self._last_error_message = message
            return {"audio_url": ""}

        self._last_error_message = None
        return {"audio_url": audio_url}

    async def close(self):
        await self.session.close()


class MusicSearcher:
    """
    用于从指定音乐平台搜索歌曲信息的工具类。

    支持的平台：
    - qq: QQ 音乐
    - netease: 网易云音乐
    - kugou: 酷狗音乐
    - kuwo: 酷我音乐
    - baidu: 百度音乐
    - 1ting: 一听音乐
    - migu: 咪咕音乐
    - lizhi: 荔枝FM
    - qingting: 蜻蜓FM
    - ximalaya: 喜马拉雅
    - 5singyc: 5sing原创
    - 5singfc: 5sing翻唱
    - kg: 全民K歌

    支持的过滤条件：
    - name: 按歌曲名称搜索（默认）
    - id: 按歌曲 ID 搜索
    - url: 按音乐地址（URL）搜索
    """

    def __init__(self):
        """初始化请求 URL 和请求头"""
        self.base_url = "https://music.txqq.pro/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
        self.session = aiohttp.ClientSession()
    async def fetch_data(self, song_name: str, platform_type: str, limit: int = 5):
        """
        向音乐接口发送 POST 请求以获取歌曲数据

        :param song_name: 要搜索的歌曲名称
        :param platform_type: 音乐平台类型，如 'qq', 'netease' 等
        :return: 返回解析后的 JSON 数据或 None
        """
        data = {
            "input": song_name,
            "filter": "name",  # 当前固定为按名称搜索
            "type": platform_type,
            "page": 1,
        }

        try:
            async with self.session.post(
                self.base_url, data=data, headers=self.headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return [
                        {
                            "id": song["songid"],
                            "name": song.get("title", "未知"),
                            "artists": song.get("author", "未知"),
                            "url": song.get("url", "无"),
                            "link": song.get("link", "无"),
                            "lyrics": song.get("lrc", "无"),
                            "cover_url": song.get("pic", "无"),
                        }
                        for song in result["songs"][:limit]
                    ]
                else:
                    logger.error(f"请求失败:{response.status}")
                    return None
        except Exception as e:
            logger.error(f"请求异常: {e}")
            return None
    async def close(self):
        await self.session.close()
