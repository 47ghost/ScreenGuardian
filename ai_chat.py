import base64
import json
import os
from datetime import datetime
from typing import Optional
import requests


class AIChatClient:
    def __init__(self, api_key: str, base_url: str, model: str, system_prompt: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.system_prompt = system_prompt or "你是 ScreenGuardian 的桌宠助手，简洁准确地回答用户问题。"

    def _build_image_part(self, image_path: Optional[str]):
        if not image_path:
            return None
        if not os.path.isfile(image_path):
            return None
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}"
            },
        }

    def chat(self, user_text: str, image_path: Optional[str] = None, temperature: float = 0.2, max_tokens: int = 1024) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        content_parts = [{"type": "text", "text": user_text}]
        image_part = self._build_image_part(image_path)
        if image_part:
            content_parts.append(image_part)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": content_parts},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
        data = resp.json()
        if "choices" not in data or not data["choices"]:
            raise RuntimeError("Empty response")
        reply = data["choices"][0]["message"]["content"]
        self._write_log(user_text=user_text, image_path=image_path, reply=reply)
        return reply

    def _write_log(self, user_text: str, image_path: Optional[str], reply: str):
        log_dir = os.path.join(os.getcwd(), "data", "log")
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, "logs.jsonl")
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "model": self.model,
            "user_input_content": user_text,
            "system_prompt": self.system_prompt,
            "image": image_path if image_path else "无上传图片",
            "reply": reply,
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    cfg_path = os.path.join(os.getcwd(), "data", "config", "model_config.json")
    if not os.path.isfile(cfg_path):
        raise RuntimeError("缺少模型配置文件 data/config/model_config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    api_key = cfg.get("api_key", "")
    base_url = cfg.get("base_url", "")
    sys_cfg = cfg.get("system_call", {}) or {}
    model = sys_cfg.get("model", "")
    system_prompt = sys_cfg.get("system_prompt", "")
    image_path = None
    user_text = """
            2026-2-4 12：35 用户在bilibili浏览徐大虾的我的世界游戏视频
            2026-2-4 12：13 用户在使用idea完成一个spirng ai项目的开发"""
    if not api_key or not base_url or not model or not user_text:
        raise RuntimeError("请在配置面板或配置文件中设置 api_key、base_url、system_call.model、user_text")
    client = AIChatClient(api_key=api_key, base_url=base_url, model=model, system_prompt=system_prompt)
    reply = client.chat(user_text=user_text, image_path=image_path)
    print(reply)



if __name__ == "__main__":
    main()
