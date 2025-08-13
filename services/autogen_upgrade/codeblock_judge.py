import json
from typing import List, Dict, Any, Optional

from utils.agent_gpt4 import AzureGPT4Chat


def _build_system_prompt() -> str:
    return (
        "你是一个代码块执行规划器。\n"
        "输入是一组从对话中抽取的代码块，每个包含 index、language、code。\n"
        "\n"
        "任务说明：\n"
        "1) 判断每个代码块是否可执行（runnable），以及语言标签与代码是否匹配（language_ok）\n"
        "2) 识别代码块意图：\n"
        "   - env_setup: 系统依赖/环境准备（如 apt-get、pip install 等）\n"
        "   - direct_exec: 直接执行的代码（包含具体逻辑，会被 autogen 直接执行）\n" 
        "   - script_run: 运行脚本命令（如 python xxx.py）\n"
        "   - other: 其他类型\n"
        "3) 抽取目标文件 target_file：\n"
        "   - 若 Python 代码包含 '# filename: xxx.py'，则 target_file=该文件名\n"
        "   - 若 Shell 代码形如 'python xxx.py' 或 'python3 xxx.py'，则 target_file=xxx.py\n"
        "4) 去重规则：如果一个代码块是直接执行的代码（包含 filename 注释），另一个代码块是运行同一脚本，则保留直接执行的代码，丢弃运行命令\n"
        "   - 同一脚本的多个运行命令仅保留一个\n"
        "   - 内容相同的代码块仅保留一个\n"
        "5) 排序规则：根据执行逻辑智能排序\n"
        "   - 环境准备（env_setup）优先执行\n"
        "   - 根据依赖关系和执行逻辑合理安排其他代码块顺序\n"
        "   - 如：数据准备 → 数据处理 → 结果输出\n"
        "   - 如：被依赖的文件先生成\n"
        "   - 如：需要先导入/定义的内容优先\n"
        "\n"
        "输出JSON格式：\n"
        "{\n"
        '  "blocks": [\n'
        '    {"index": 0, "keep": true, "intent": "env_setup", "target_file": null},\n'
        '    {"index": 1, "keep": true, "intent": "direct_exec", "target_file": "convert.py"}\n'
        '  ],\n'
        '  "order": [0, 1]\n'
        "}\n"
        "\n"
        "示例1 - 智能重排序（环境准备 + 直接执行）：\n"
        "输入: [\n"
        '  {"index": 0, "language": "python", "code": "# filename: convert.py\\nimport os\\nfrom spatie.pdf_to_text import Pdf\\nprint(\\"converting\\")"},\n'
        '  {"index": 1, "language": "sh", "code": "apt-get update && apt-get install -y poppler-utils"}\n'
        "]\n"
        "输出: {\n"
        '  "blocks": [{"index": 1, "keep": true, "intent": "env_setup", "target_file": null}, {"index": 0, "keep": true, "intent": "direct_exec", "target_file": "convert.py"}],\n'
        '  "order": [1, 0]\n'
        "}\n"
        "\n"
        "示例2 - 直接执行 + 运行脚本去重：\n"
        "输入: [\n"
        '  {"index": 0, "language": "python", "code": "# filename: test.py\\nprint(\\"test\\")"},\n'
        '  {"index": 1, "language": "sh", "code": "python test.py"}\n'
        "]\n"
        "输出: {\n"
        '  "blocks": [{"index": 0, "keep": true, "intent": "direct_exec", "target_file": "test.py"}, {"index": 1, "keep": false, "intent": "script_run", "target_file": "test.py"}],\n'
        '  "order": [0]\n'
        "}\n"
        "\n"
        "只输出JSON，不要其他文字。"
    )


def _build_user_prompt(raw_blocks: List[Dict[str, Any]]) -> str:
    return f"代码块列表：\n{json.dumps(raw_blocks, ensure_ascii=False, indent=2)}\n\n请分析并输出JSON："


def llm_judge_code_blocks(
    raw_blocks: List[Dict[str, Any]],
    message_list: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    使用 LLM 对代码块进行可执行性判断、语言匹配、去重与排序。

    Args:
        raw_blocks: [{"index": int, "language": str, "code": str}, ...]
        message_list: 额外上下文（可选，不需要可传 None）。

    Returns:
        Dict，包含 blocks/order。
    """
    system_prompt = _build_system_prompt()

    if message_list is None:
        message_list = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _build_user_prompt(raw_blocks)},
        ]
    else:
        # 在传入自定义 message_list 的情况下，保证包含系统与用户需求
        message_list = list(message_list)
        message_list.insert(0, {"role": "system", "content": system_prompt})
        message_list.append({"role": "user", "content": _build_user_prompt(raw_blocks)})

    agent = AzureGPT4Chat()

    try:
        content = agent.chat_with_message(
            message=message_list,
            json_format=True
        )
        # chat_with_message 返回解析后的 dict
        if isinstance(content, str):
            result = json.loads(content)
        else:
            result = content
            
        # 基本健壮性：若缺 key 则补齐
        if "blocks" not in result:
            result["blocks"] = []
        if "order" not in result:
            result["order"] = []
        return result
    except Exception as e:
        print(f"LLM 判定失败: {e}")
        # 兜底：全部保留，按原始顺序
        n = len(raw_blocks)
        return {
            "blocks": [
                {"index": i, "keep": True, "intent": "other", "target_file": None}
                for i in range(n)
            ],
            "order": list(range(n))
        }


def process_and_filter_code_blocks(code_blocks) -> List:
    """
    处理代码块：使用 LLM 判定、去重与排序，返回处理后的代码块列表。
    
    Args:
        code_blocks: 从 autogen code_extractor 提取的代码块列表
        
    Returns:
        List: 处理后的代码块列表（已去重、排序）
    """
    if len(code_blocks) == 0:
        return []
    
    try:
        # 使用 LLM 对代码块进行判定、去重与排序
        raw_blocks = [
            {"index": i, "language": getattr(cb, "language", None), "code": getattr(cb, "code", None)}
            for i, cb in enumerate(code_blocks)
        ]
        judge = llm_judge_code_blocks(raw_blocks)
        
        # 解析判定结果
        blocks_info = {item.get("index"): item for item in judge.get("blocks", [])}
        ordered = judge.get("order", list(range(len(code_blocks))))
        keep_set = {idx for idx, info in blocks_info.items() if info.get("keep", True)}
        
        # 若 blocks_info 为空，默认全部保留
        if not blocks_info:
            keep_set = set(range(len(code_blocks)))
        
        # 过滤与重排
        selected_indexes = [idx for idx in ordered if idx in keep_set and 0 <= idx < len(code_blocks)]
        
        # 去重（防止 LLM 输出重复 index）
        seen = set()
        selected_indexes = [idx for idx in selected_indexes if not (idx in seen or seen.add(idx))]
        
        if len(selected_indexes) == 0:
            return []
        
        return [code_blocks[idx] for idx in selected_indexes]
        
    except Exception as e:
        print(f"代码块处理失败: {e}")
        # 兜底：返回原始代码块列表
        return code_blocks 