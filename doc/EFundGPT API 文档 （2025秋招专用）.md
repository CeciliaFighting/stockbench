# EFundGPT API 文档（2025 秋招专用）

<!-- Converted from doc/EFundGPT API 文档 （2025秋招专用）.pdf using pdftotext. -->

## 快速开始

使用与 OpenAI 兼容的 API 格式，通过调整部分调用参数，即可访问易方达内部统一的大模型接口。需要调整的参数包括：

| 参数       | 值                              |
| ---------- | ------------------------------- |
| `base_url` | `https://aigc.efunds.com.cn/v1` |
| `api_key`  | 联系带教导师获取                |

## 可用模型列表

### 内部模型

百万输入 / 输出 token 内部系统计费单价见下表。

#### LLM

| 模型名称                | 模型描述                                 | 参数量  | 百万输入 / 输出 token 单价 |
| ----------------------- | ---------------------------------------- | ------- | -------------------------- |
| `EFundGPT-air`          | 保证效果底线的前提下，响应最快的语言模型 | 14~72B  | ￥0.8 / ￥2.4              |
| `EFundGPT-pro`          | 推理速度与效果平衡的语言模型             | 72B     | ￥0.8 / ￥2.4              |
| `EFundGPT-max`          | 保证性能底线的前提下，效果最佳的语言模型 | 72~300B | ￥3 / ￥12                 |
| `EFundGPT-ultra`        | 资源消耗较大的超大参数量模型             | 300B+   | ￥4 / ￥16                 |
| `EFundGPT-thinking-max` | 强推理模型                               | 32~671B | ￥4 / ￥16                 |

#### VLM

| 模型名称          | 模型描述                                     | 参数量 | 百万输入 / 输出 token 单价 |
| ----------------- | -------------------------------------------- | ------ | -------------------------- |
| `EFundGPT-vl-air` | 保证效果底线的前提下，响应最快的视觉语言模型 | 14~72B | ￥1.6 / ￥4.8              |
| `EFundGPT-vl-pro` | 推理速度与效果平衡的语言模型                 | 72B    | ￥1.6 / ￥4.8              |
| `EFundGPT-vl-max` | 保证性能底线的前提下，效果最佳的视觉语言模型 | 72B+   | ￥1.6 / ￥4.8              |

#### Embedding

| 模型名称                     | 参数量 | 最大输入长度 | 输出维度 | 说明                                                                                                   | 百万输入 / 输出 token 单价 |
| ---------------------------- | ------ | ------------ | -------- | ------------------------------------------------------------------------------------------------------ | -------------------------- |
| `EFundGPT-emb-qwen3-0.6b-v2` | 0.6B   | 32k          | 1024     | 2025 年推出的 Qwen3 文本向量化模型，具有更高的 MTEB 评分（多语言 64.34，中文 66.33），兼容更长的输入。 | ￥0.14 / ￥0.14            |

#### Rerank

| 模型名称            | 参数量 | 最大输入长度 | 说明                 | 百万输入 / 输出 token 单价 |
| ------------------- | ------ | ------------ | -------------------- | -------------------------- |
| `EFundGPT-reranker` | 0.6B   | 8k           | 别名：`bge-reranker` | ￥0.7 / ￥0.7              |

### 外部模型

百万输入 / 输出 token 单价见下表。模型名称下面是输入 / 输出百万 Tokens 单价，价格来源于官方文档（Azure / 智谱 / 通义 / DeepSeek），Azure 单价按汇率 `$1 = ￥7` 近似计算。

| 类别         | Azure                                                                                                                                                                                                                                                                                | 智谱                                                             | 通义                                                       | DeepSeek                                          | 豆包                                                                      |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------- |
| VLM          | `gpt-4o`<br>￥35 / ￥105                                                                                                                                                                                                                                                             | `glm-4v`<br>￥50 / ￥50                                          | -                                                          | -                                                 | `Doubao-Seed-1.6`<br>￥0.8 / ￥2.4<br>256k tokens，支持图片模态，支持思考 |
| LLM-慢思考   | `o4-mini`<br>￥7.7 / ￥30.8<br><br>`o3`<br>￥14 / ￥56<br><br>`o3-mini`<br>￥8.47 / ￥33.88<br><br>`o1-preview`<br>￥115.5 / ￥462<br><br>`o1-mini`<br>￥8.47 / ￥33.88                                                                                                              | -                                                                | -                                                          | `deepseek-r1` / `deepseek-reasoner`<br>￥4 / ￥16 | -                                                                         |
| LLM-长上下文 | -                                                                                                                                                                                                                                                                                    | `glm-4-long`<br>￥1 / ￥1<br>1M tokens；GLM 全系列支持 128k 输入 | `qwen-long`<br>￥0.5 / ￥2<br>10M tokens                   | -                                                 | -                                                                         |
| LLM-主力     | `gpt-5.1` / `gpt-5.1-chat`<br>￥8.75 / ￥70<br><br>`gpt-5` / `gpt-5-chat`<br>￥8.75 / ￥70<br><br>`gpt-5-mini`<br>￥1.75 / ￥14<br><br>`gpt-5-nano`<br>￥0.35 / ￥2.8<br><br>`gpt-4.1`<br>￥14 / ￥56<br><br>`gpt-4.1-mini`<br>￥2.8 / ￥11.2<br><br>`gpt-4.1-nano`<br>￥0.7 / ￥2.8 | `glm-4`<br>￥100 / ￥100                                         | `qwen-max-latest`<br>￥40 / ￥120                          | `deepseek-v3`<br>￥4 / ￥12                       | -                                                                         |
| LLM-速度快   | -                                                                                                                                                                                                                                                                                    | `glm-4-air`<br>￥1 / ￥1<br><br>`glm-4-flash`<br>￥0 / ￥0       | `qwen-plus`<br>￥4 / ￥12<br><br>`qwen-turbo`<br>￥2 / ￥6 | -                                                 | -                                                                         |
| Embedding    | `text-embedding-ada-002`<br>￥0.7                                                                                                                                                                                                                                                    | -                                                                | `text-embedding-v1`<br>￥0.7                               | -                                                 | `Doubao-embedding`<br>￥0.5                                               |

## Curl 请求示例

> 注意：`Efunds-User-Name` 请填写实际调用者的用户名（邮箱前缀）。下面示例中的 header value 必须替换为实际值，且不能为中文。

### LLM

```bash
curl {base_url}/chat/completions \
  -H 'Authorization: Bearer {api_key}' \
  -H 'Efunds-User-Name: SX-{用户名}' \
  -H 'Efunds-Acc-Token: SX-{用户名}' \
  -H 'Efunds-Source: 2025-SX' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "EFundGPT-air",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "你好"}
    ],
    "temperature": 1.0,
    "stream": false
  }'
```

执行结果：

```json
{
  "id": "716",
  "object": "chat.completion",
  "created": 1721006905,
  "model": "EFundGPT-air",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "你好！很高兴为你提供帮助。"
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 20,
    "total_tokens": 27,
    "completion_tokens": 7
  }
}
```

### VLM

```bash
curl {base_url}/chat/completions \
  -H 'Authorization: Bearer {api_key}' \
  -H 'Efunds-User-Name: SX-{用户名}' \
  -H 'Efunds-Acc-Token: SX-{用户名}' \
  -H 'Efunds-Source: 2025-SX' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "EFundGPT-vl-air",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "解释一下图片的内容"},
          {"type": "image_url", "image_url": {"url": "data:image/png;base64,<base64_png_data>"}}
        ]
      }
    ],
    "temperature": 1.0,
    "stream": false
  }'
```

执行结果：

```json
{
  "id": "chatcmpl-3f4cc549010f4ee5a598d58ba883f05a",
  "object": "chat.completion",
  "created": 1759997910,
  "model": "EFundGPT-vl-max",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "reasoning_content": null,
        "content": "这张图片展示了一幅风景画。画中有蓝天、白云和树木，给人一种宁静自然的感觉。画的右上角有“MENGER”的字样，可能是艺术家的名字或者画作的标题。",
        "tool_calls": []
      },
      "logprobs": null,
      "finish_reason": "stop",
      "stop_reason": null
    }
  ],
  "usage": {
    "prompt_tokens": 30,
    "total_tokens": 74,
    "completion_tokens": 44,
    "prompt_tokens_details": null
  },
  "prompt_logprobs": null
}
```

### Embedding

```bash
curl {base_url}/embeddings \
  -H 'Authorization: Bearer {api_key}' \
  -H 'Efunds-User-Name: SX-{用户名}' \
  -H 'Efunds-Acc-Token: SX-{用户名}' \
  -H 'Efunds-Source: 2025-SX' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "EFundGPT-emb-qwen3-0.6b",
    "input": [
      "这是一个示例输入文本，用于获取嵌入向量",
      "This is a sample input text for obtaining embedded vectors"
    ]
  }'
```

执行结果：

```json
{
  "id": "embd-10654ff3f4dfbd811dec8de0d7441203",
  "object": "list",
  "created": 1759999436,
  "model": "qwen3-embedding-0.6b",
  "data": [
    {
      "index": 0,
      "object": "embedding",
      "embedding": [-0.02001953125, "...", 0.0322265625]
    },
    {
      "index": 1,
      "object": "embedding",
      "embedding": [-0.0228271484375, "...", 0.01470947265625]
    }
  ],
  "usage": {
    "prompt_tokens": 24,
    "total_tokens": 24,
    "completion_tokens": 0,
    "prompt_tokens_details": null
  }
}
```

### Reranker

```bash
curl {base_url}/rerank \
  -H 'Authorization: Bearer {api_key}' \
  -H 'Efunds-User-Name: SX-{用户名}' \
  -H 'Efunds-Acc-Token: SX-{用户名}' \
  -H 'Efunds-Source: 2025-SX' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "EFundGPT-reranker",
    "query": "示例查询文本",
    "documents": [
      "这是一个文档示例，用于重新排序。",
      "This is a document example for reranking."
    ]
  }'
```

执行结果：

```json
{
  "id": "rerank-bge-reranker-1113300224",
  "model": "bge-reranker",
  "results": [
    {
      "index": 0,
      "document": {
        "text": "这是一个文档示例，用于重新排序。"
      },
      "relevance_score": 0.05654813492876745
    },
    {
      "index": 1,
      "document": {
        "text": "This is a document example for reranking."
      },
      "relevance_score": 0.022933564232383716
    }
  ],
  "usage": {
    "total_tokens": 32
  }
}
```

### Jina Search / Read

```bash
curl -X POST f"{base_url}/searches/jina-searcher" \
  -H "Content-Type: application/json" \
  -H 'Authorization: Bearer {api_key}' \
  -H 'Efunds-User-Name: SX-{用户名}' \
  -H 'Efunds-Acc-Token: SX-{用户名}' \
  -H 'Efunds-Source: 2025-SX' \
  -d '{"q": "AI 大模型的应用"}'

curl -X POST f"{base_url}/searches/jina-reader" \
  -H "Content-Type: application/json" \
  -H 'Authorization: Bearer {api_key}' \
  -H 'Efunds-User-Name: SX-{用户名}' \
  -H 'Efunds-Acc-Token: SX-{用户名}' \
  -H 'Efunds-Source: 2025-SX' \
  -d '{"url": "www.baidu.com"}'
```

## 通过 OpenAI Python SDK 调用

> 注意：`Efunds-User-Name` 请填写实际调用者的用户名（邮箱前缀）。这些 header value 都必须是英文，不能填写中文。

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://aigc.efunds.com.cn/v1",
    api_key="******",
)

resp = client.chat.completions.create(
    model="EFundGPT-air",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "你好"},
    ],
    temperature=1.0,
    stream=False,
    extra_headers={
        "Efunds-User-Name": "SX-{用户名}",
        "Efunds-Acc-Token": "SX-{用户名}",
        "Efunds-Source": "2025-SX",
    },
)

print(resp.choices[0].message.content)  # 你好！有什么我能帮助你的吗？
```
