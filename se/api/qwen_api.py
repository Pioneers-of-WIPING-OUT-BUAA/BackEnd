# https://se-wj.oss-cn-beijing.aliyuncs.com/0%2F1748156298439%2F114514.jpg?OSSAccessKeyId=LTAI5t9ZB2mkrXDjFdYun2Wx&Expires=1748188729&Signature=IeLGEnfYABXtx9yyj5AdiBMu30I%3D

from openai import OpenAI
from backend.settings import LLM_API_KEY
import os

def infer(url1, url2, prompt):
    client = OpenAI(
        api_key=LLM_API_KEY,
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    )

    if url2 == None:
        completion = client.chat.completions.create(
            # model="Qwen/Qwen2.5-VL-32B-Instruct", 
            model="doubao-1-5-vision-pro-32k-250115",
            messages=[
            {"role":"system","content":[{"type": "text", "text": "You are a helpful assistant."}]},
            {"role": "user","content": [
                {"type": "image_url","image_url": {"url": f"{url1}"},},
                {"type": "text", "text": f"{prompt}"},
                    ],
                }
            ],
        )
    else:
        completion = client.chat.completions.create(
            # model="Qwen/Qwen2.5-VL-32B-Instruct", 
            model="doubao-1-5-vision-pro-32k-250115",
            messages=[
            {"role":"system","content":[{"type": "text", "text": "You are a helpful assistant."}]},
            {"role": "user","content": [
                {"type": "image_url","image_url": {"url": f"{url1}"},},
                {"type": "image_url","image_url": {"url": f"{url2}"},},
                {"type": "text", "text": f"{prompt}"},
                    ],
                }
            ],
        )

    return completion.choices[0].message.content


def detect_stranger(url1, url2):
    PROMPT = "若两张照片中均存在两个明显的人脸，请判断二者是否属于同一个人，属于同一个人的话回答“是”；否则请回答“否”。如果图片中没有明显的人脸，请回答“无法回答”。"
    result = infer(url1, url2, PROMPT)
    print(f"detect_stranger result: {result}")
    return True if "否" in result else False

def detect_fire(url):
    PROMPT = "请判断图片中是否存在明火，存在明火的话回答“是”；否则请回答“否”。注意，如果图中存在纸，并且纸上画有火的话，也请回答“是”。"
    result = infer(url, None, PROMPT)
    print(f"detect_fire result: {result}")
    return True if "是" in result else False

def detect_smoke(url):
    PROMPT = "请判断图片中是否存在烟雾，存在烟雾的话回答“是”；否则请回答“否”。注意，如果图中存在纸，并且纸上画有烟雾的话，也请回答“是”。"
    result = infer(url, None, PROMPT)
    print(f"detect_smoke result: {result}")
    return True if "是" in result else False

def detect_rubbish(url):
    PROMPT = "请判断图片中是否存在瓶装水，存在瓶装水的话回答“是”；否则请回答“否”。"
    result = infer(url, None, PROMPT)
    print(f"detect_rubbish result: {result}")
    return True if "是" in result else False


def voice2plan(command):
    def infer(prompt):
        client = OpenAI(
            api_key=LLM_API_KEY,
            base_url="https://ark.cn-beijing.volces.com/api/v3",
        )
        completion = client.chat.completions.create(
            # model="Qwen/Qwen2.5-VL-32B-Instruct",
            model="doubao-1-5-vision-pro-32k-250115",
            messages=[
                {"role": "system", "content": [{"type": "text", "text": "You are a helpful assistant."}]},
                {"role": "user", "content": [
                    {"type": "text", "text": f"{prompt}"},
                ]}
            ]
        )
        return completion.choices[0].message.content

    PROMPT = f"""
    你是机器人控制指令转换器。请根据下表，从“唯一且最合适”的关键字中**挑选一个**，并 **只输出该关键字本身**（小写、无空格、无标点）。  
    如无法映射，返回 r（停止）。

    可选关键字及语义  
    - r          : 停止
    - w          : 前进
    - s          : 后退
    - a          : 左移
    - d          : 右移
    - q          : 向左转
    - e          : 向右转
    - arm_out    : 伸出机械臂
    - arm_in     : 收回机械臂
    - arm_up     : 抬起机械臂
    - arm_down   : 放下机械臂
    - grip       : 抓取
    - release    : 释放
    - arm_stop   : 停止机械臂移动

    **示例（输入 → 输出）**
    停下来                → r
    往前走两米             → w
    向左转 90 度            → q
    把机械臂伸出去          → arm_out
    抓住那个瓶子            → grip

    —— 现在开始 ——
    中文指令: {command}
    """
    result = infer(PROMPT)
    DIRECTION = [
        "r", # 停止
        "w", # 前进
        "s", # 后退
        "a", # 左移
        "d", # 右移
        "q", # 向左转
        "e", # 向右转
        "arm_out", # 伸出机械臂
        "arm_in", # 收回机械臂
        "arm_up", # 抬起机械臂
        "arm_down", # 放下机械臂
        "grip", # 抓取
        "release", # 释放
        "arm_stop" # 停止机械臂移动
    ]
    result = result.strip().lower()
    print(f"voice2plan result: {result}")
    if result in DIRECTION:
        return result
    else:
        return "r"

if __name__ == "__main__":
    url1 = "https://bkimg.cdn.bcebos.com/pic/fd039245d688d43f879437695e4bc51b0ef41ad58da9"
    url2 = "https://img1.baidu.com/it/u=1787943861,3868475152&fm=253&fmt=auto&app=138&f=JPEG?w=500&h=657"

    print(detect_stranger(url1, url2))
