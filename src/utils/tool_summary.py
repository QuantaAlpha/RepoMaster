from src.utils.agent_gpt4 import AzureGPT4Chat
from textwrap import dedent

def generate_summary(messages):
    """Generate summary for a set of messages"""
    system_prompt = dedent(f"""
    You are a helpful assistant that summarizes the conversation context.
    """)
    
    # Use LLM to generate summary
    summary_prompt = dedent(f"""
    Please extract all key results returned by tools based on the conversation history in detail, ensuring the summary:
    1. Completely preserve all important facts, core data points and key indicators in the original data
    2. Do not omit any key numbers, dates, statistical data and their meanings
    3. Preserve analysis conclusions, insights and reasoning processes as they are, without simplification or generalization
    4. Keep all information that affects decisions, including risk factors, limitations and precautions
    5. Present background information completely, such as URLs, time periods, locations, related people and events
    6. For tables, lists and structured data, maintain their integrity and original format
    
    Please note: This summary should be a complete record of the original content, not a simplified version. Rather be verbose than miss important details, especially analysis conclusions and core findings.

    <history_messages>
    {messages}
    </history_messages>
    """)

    # Use AzureGPT4Chat to generate summary
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