from functools import lru_cache

from django.conf import settings
from openai import APIError, OpenAI


class AIServiceError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _client(api_key, timeout):
    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=timeout,
        max_retries=0,
    )


def get_client():
    if not settings.OPENROUTER_API_KEY:
        raise AIServiceError("OpenRouter API key is not configured.")
    return _client(settings.OPENROUTER_API_KEY, settings.OPENROUTER_TIMEOUT)


def _complete(content):
    try:
        completion = get_client().chat.completions.create(
            model=settings.OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": "Follow the requested output format exactly."},
                {"role": "user", "content": content},
            ],
            temperature=0,
            max_tokens=64,
        )
    except APIError as exc:
        raise AIServiceError("OpenRouter request failed.") from exc
    if not completion.choices or not completion.choices[0].message.content:
        raise AIServiceError("OpenRouter returned an empty response.")
    return completion.choices[0].message.content.strip()


def infer(url1, url2, prompt):
    content = [
        {"type": "image_url", "image_url": {"url": url}}
        for url in (url1, url2) if url is not None
    ]
    content.append({"type": "text", "text": prompt})
    return _complete(content)


def _answer(result):
    answer = result.strip().strip("。.!！ \\n")
    if answer not in {"是", "否", "无法回答"}:
        raise AIServiceError("OpenRouter returned an invalid detection result.")
    return answer


def detect_stranger(url1, url2):
    prompt = "判断两张照片中的人脸是否属于同一个人。属于同一个人只回答是，否则只回答否。没有明显人脸时只回答无法回答。"
    return _answer(infer(url1, url2, prompt)) == "否"


def detect_fire(url):
    prompt = "判断图片中是否存在明火，包括纸上绘制的火焰。只回答是或否。"
    return _answer(infer(url, None, prompt)) == "是"


def detect_smoke(url):
    prompt = "判断图片中是否存在烟雾，包括纸上绘制的烟雾。只回答是或否。"
    return _answer(infer(url, None, prompt)) == "是"


def detect_rubbish(url):
    return _answer(infer(url, None, "判断图片中是否存在瓶装水。只回答是或否。")) == "是"


def voice2plan(command):
    directions = {
        "r": "停止", "w": "前进", "s": "后退", "a": "左移", "d": "右移",
        "q": "向左转", "e": "向右转", "arm_out": "伸出机械臂",
        "arm_in": "收回机械臂", "arm_up": "抬起机械臂", "arm_down": "放下机械臂",
        "grip": "抓取", "release": "释放", "arm_stop": "停止机械臂移动",
    }
    prompt = (
        "你是机器人控制指令转换器。根据以下映射只输出一个小写关键字，"
        "不输出解释、空格或标点。无法映射时输出 r。\n"
        + "\n".join(f"{key}: {value}" for key, value in directions.items())
        + f"\n中文指令: {command}"
    )
    result = _complete([{"type": "text", "text": prompt}]).lower()
    return result if result in directions else "r"
