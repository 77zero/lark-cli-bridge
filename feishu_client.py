"""
飞书消息客户端
封装 lark-oapi SDK 的消息发送、卡片更新、图片下载等功能
"""

import json
import os
import tempfile
from typing import Optional

import lark_oapi as lark
from lark_oapi.api.im.v1 import *


class FeishuClient:
    """飞书 API 客户端，处理消息收发和卡片交互"""

    def __init__(self, client: lark.Client):
        self.client = client

    # ── 发送消息 ──────────────────────────────────────────────

    async def send_text_to_user(self, open_id: str, text: str) -> str:
        """发送文本消息给指定用户，返回 message_id"""
        content = json.dumps({"text": text}, ensure_ascii=False)
        return await self._send("open_id", open_id, "text", content)

    async def reply_text(self, message_id: str, text: str) -> str:
        """回复文本消息，返回 message_id"""
        content = json.dumps({"text": text}, ensure_ascii=False)
        return await self._reply(message_id, "text", content)

    # ── 卡片消息 ──────────────────────────────────────────────

    async def send_card_to_user(
        self, open_id: str, content: str = "", loading: bool = False
    ) -> str:
        """发送卡片消息给用户，返回 card_message_id"""
        elements = self._build_card_elements(content, loading)
        card_content = self._build_card_json(elements)
        return await self._send("open_id", open_id, "interactive", card_content)

    async def reply_card(
        self, message_id: str, content: str = "", loading: bool = False
    ) -> str:
        """回复卡片消息，返回 card_message_id"""
        elements = self._build_card_elements(content, loading)
        card_content = self._build_card_json(elements)
        return await self._reply(message_id, "interactive", card_content)

    # ── 卡片更新 ──────────────────────────────────────────────

    async def update_card(self, message_id: str, content: str) -> None:
        """更新卡片内容（patch）"""
        elements = self._build_card_elements(content, loading=False)
        card_content = self._build_card_json(elements)
        await self._patch(message_id, card_content)

    async def update_card_with_buttons(
        self, message_id: str, content: str,
        buttons: list[dict], flow: bool = True
    ) -> None:
        """更新卡片内容并附加按钮"""
        elements = self._build_card_elements(content, loading=False)
        # 添加按钮
        btn_elements = []
        for btn in buttons:
            btn_elements.append({
                "tag": "button",
                "text": {"tag": "plain_text", "content": btn["text"]},
                "type": "primary" if btn is buttons[0] else "default",
                "value": btn.get("value", {}),
            })
        if btn_elements:
            if flow:
                elements.append({
                    "tag": "action",
                    "actions": [
                        {"tag": "button", **b} for b in btn_elements
                    ],
                    "layout": "flow",
                })
            else:
                for b in btn_elements:
                    elements.append({
                        "tag": "action",
                        "actions": [b],
                    })
        card_content = self._build_card_json(elements)
        await self._patch(message_id, card_content)

    # ── 图片处理 ──────────────────────────────────────────────

    async def download_image(self, message_id: str, image_key: str) -> Optional[str]:
        """下载飞书消息中的图片，返回本地临时文件路径"""
        try:
            req = GetMessageResourceReq.builder() \
                .message_id(message_id) \
                .file_key(image_key) \
                .type("image") \
                .build()
            resp = self.client.im.v1.message_resource.get(req)
            if not resp.success():
                print(f"[image] 下载失败: {resp.msg}", flush=True)
                return None

            suffix = ".png"
            content_type = resp.file.headers.get("Content-Type", "")
            if "jpeg" in content_type or "jpg" in content_type:
                suffix = ".jpg"
            elif "gif" in content_type:
                suffix = ".gif"

            fd, path = tempfile.mkstemp(suffix=suffix, prefix="feishu_img_")
            with os.fdopen(fd, "wb") as f:
                f.write(resp.file.read())
            return path
        except Exception as e:
            print(f"[image] 下载异常: {e}", flush=True)
            return None

    # ── 内部方法 ──────────────────────────────────────────────

    async def _send(
        self, receive_id_type: str, receive_id: str,
        msg_type: str, content: str
    ) -> str:
        """发送消息底层方法"""
        req = CreateMessageReq.builder() \
            .receive_id_type(receive_id_type) \
            .request_body(
                CreateMessageReqBody.builder()
                    .receive_id(receive_id)
                    .msg_type(msg_type)
                    .content(content)
                    .build()
            ) \
            .build()
        resp = self.client.im.v1.message.create(req)
        if not resp.success():
            raise RuntimeError(f"发送消息失败: {resp.msg}")
        return resp.data.message_id

    async def _reply(self, message_id: str, msg_type: str, content: str) -> str:
        """回复消息底层方法"""
        req = ReplyMessageReq.builder() \
            .message_id(message_id) \
            .request_body(
                ReplyMessageReqBody.builder()
                    .content(content)
                    .msg_type(msg_type)
                    .build()
            ) \
            .build()
        resp = self.client.im.v1.message.reply(req)
        if not resp.success():
            raise RuntimeError(f"回复消息失败: {resp.msg}")
        return resp.data.message_id

    async def _patch(self, message_id: str, content: str) -> None:
        """更新消息（patch）底层方法"""
        req = PatchMessageReq.builder() \
            .message_id(message_id) \
            .request_body(
                PatchMessageReqBody.builder()
                    .content(content)
                    .build()
            ) \
            .build()
        resp = self.client.im.v1.message.patch(req)
        if not resp.success():
            raise RuntimeError(f"更新消息失败: {resp.msg}")

    # ── 卡片构建 ──────────────────────────────────────────────

    @staticmethod
    def _build_card_elements(content: str, loading: bool) -> list[dict]:
        """构建卡片元素列表"""
        elements = []
        if loading:
            elements.append({
                "tag": "markdown",
                "content": content or "⏳ 思考中...",
            })
            if not content:
                elements.append({
                    "tag": "hr",
                })
                elements.append({
                    "tag": "note",
                    "elements": [{"tag": "plain_text", "content": "正在处理，请稍候..."}],
                })
        else:
            # 将内容分段，超过 4000 字符则截断
            display = content
            if len(content) > 4000:
                display = content[:4000] + "\n\n...（内容过长已截断）"
            elements.append({
                "tag": "markdown",
                "content": display,
            })
        return elements

    @staticmethod
    def _build_card_json(elements: list[dict]) -> str:
        """构建卡片消息的完整 JSON 内容"""
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "CLI Bridge"},
                "template": "blue",
            },
            "elements": elements,
        }
        return json.dumps(card, ensure_ascii=False)
