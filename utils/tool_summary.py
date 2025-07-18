from utils.agent_gpt4 import AzureGPT4Chat
from textwrap import dedent

def generate_summary(messages):
    """为一组消息生成摘要"""
    system_prompt = dedent(f"""
    You are a helpful assistant that summarizes the conversation context.
    """)
    
    # 使用LLM生成摘要
    summary_prompt = dedent(f"""
    请基于对话历史详细提取工具返回的全部关键结果，确保摘要：
    1. 完整保留原始数据中的所有重要事实、核心数据点和关键指标
    2. 不省略任何关键数字、日期、统计数据及其所代表的含义
    3. 原样保留分析结论、见解和推理过程，不进行简化或概括
    4. 保持所有对决策有影响的信息，包括风险因素、限制条件和注意事项
    5. 完整呈现背景信息，如URL、时间段、地点、相关人物和事件
    6. 对于表格、列表和结构化数据，保持其完整性和原始格式
    
    请注意：此摘要应当是对原始内容的完整记录，而非简化版本。宁可冗长也不要遗漏重要细节，尤其是分析结论和核心发现。

    <history_messages>
    {messages}
    </history_messages>
    """)

    # 使用AzureGPT4Chat生成摘要
    llm = AzureGPT4Chat()
    summary = llm.chat_with_message_format(question=summary_prompt, system_prompt=system_prompt)
    return summary


if __name__ == "__main__":
    messages = [
        {"role": "user", "content": "What is the capital of France?"},
        {"role": "assistant", "content": "The capital of France is Paris."},
    ]
    tool_responses = "The capital of France is Paris."
    print(generate_summary(messages))