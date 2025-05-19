from typing import List, Dict, Any, Optional, Union, Tuple, Callable
import copy
import re


class MessageUtils:
    """AutoGen消息处理工具库
    
    提供一系列方法用于读取、添加、修改和删除AutoGen消息列表中的元素。
    特别处理工具调用、函数调用和角色信息等复杂情况。
    """
    
    @staticmethod
    def deep_copy_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """创建消息列表的深拷贝，避免修改原始数据"""
        return copy.deepcopy(messages)
    
    @staticmethod
    def get_message_by_index(messages: List[Dict[str, Any]], index: int) -> Dict[str, Any]:
        """通过索引获取消息"""
        if 0 <= index < len(messages):
            return messages[index]
        raise IndexError(f"索引 {index} 超出消息列表范围 (0-{len(messages)-1})")
    
    @staticmethod
    def get_messages_by_role(messages: List[Dict[str, Any]], role: str) -> List[Dict[str, Any]]:
        """获取指定角色的所有消息"""
        return [msg for msg in messages if msg.get("role") == role]
    
    @staticmethod
    def get_messages_by_name(messages: List[Dict[str, Any]], name: str) -> List[Dict[str, Any]]:
        """获取指定名称的所有消息"""
        return [msg for msg in messages if msg.get("name") == name]
    
    @staticmethod
    def get_last_message(messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """获取最后一条消息"""
        return messages[-1] if messages else None
    
    @staticmethod
    def get_tool_calls(message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取消息中的工具调用列表"""
        return message.get("tool_calls", [])
    
    @staticmethod
    def get_function_call(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取消息中的函数调用(旧版API)"""
        return message.get("function_call")
    
    @staticmethod
    def get_tool_responses(message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取消息中的工具响应列表"""
        return message.get("tool_responses", [])
    
    @staticmethod
    def find_related_tool_response(messages: List[Dict[str, Any]], tool_call_id: str) -> Optional[Dict[str, Any]]:
        """查找与特定工具调用ID相关的工具响应"""
        for msg in messages:
            for response in msg.get("tool_responses", []):
                if response.get("tool_call_id") == tool_call_id:
                    return response
        return None
    
    @staticmethod
    def find_related_tool_call(messages: List[Dict[str, Any]], tool_call_id: str) -> Optional[Dict[str, Any]]:
        """查找与特定工具调用ID相关的工具调用"""
        for msg in messages:
            for tool_call in msg.get("tool_calls", []):
                if tool_call.get("id") == tool_call_id:
                    return tool_call
        return None
    
    @staticmethod
    def find_message_with_tool_call_id(messages: List[Dict[str, Any]], tool_call_id: str) -> Optional[Dict[str, Any]]:
        """查找包含特定工具调用ID的消息"""
        for msg in messages:
            for tool_call in msg.get("tool_calls", []):
                if tool_call.get("id") == tool_call_id:
                    return msg
        return None
    
    @staticmethod
    def find_message_with_tool_response_id(messages: List[Dict[str, Any]], tool_call_id: str) -> Optional[Dict[str, Any]]:
        """查找包含特定工具响应ID的消息"""
        for msg in messages:
            for response in msg.get("tool_responses", []):
                if response.get("tool_call_id") == tool_call_id:
                    return msg
        return None
    
    @staticmethod
    def add_message(messages: List[Dict[str, Any]], message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """添加新消息到消息列表"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        new_messages.append(message)
        return new_messages
    
    @staticmethod
    def update_message(messages: List[Dict[str, Any]], index: int, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """更新指定索引的消息"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            new_messages[index] = message
            return new_messages
        raise IndexError(f"索引 {index} 超出消息列表范围 (0-{len(messages)-1})")
    
    @staticmethod
    def delete_message(messages: List[Dict[str, Any]], index: int) -> List[Dict[str, Any]]:
        """删除指定索引的消息"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            # 检查是否需要删除相关的工具响应
            message = new_messages[index]
            # 如果删除的消息包含工具调用，需要删除相关的工具响应消息
            if "tool_calls" in message:
                tool_call_ids = [tc.get("id") for tc in message.get("tool_calls", [])]
                new_messages = MessageUtils._remove_related_tool_responses(new_messages, tool_call_ids)
            
            # 如果删除的消息是工具响应，可能需要从其他消息中删除tool_responses字段
            if message.get("role") == "tool":
                tool_call_id = message.get("tool_call_id")
                if tool_call_id:
                    for msg in new_messages:
                        if "tool_responses" in msg:
                            msg["tool_responses"] = [
                                tr for tr in msg["tool_responses"] 
                                if tr.get("tool_call_id") != tool_call_id
                            ]
                            # 如果tool_responses为空，删除该字段
                            if not msg["tool_responses"]:
                                del msg["tool_responses"]
            
            # 删除消息
            del new_messages[index]
            return new_messages
        raise IndexError(f"索引 {index} 超出消息列表范围 (0-{len(messages)-1})")
    
    @staticmethod
    def _remove_related_tool_responses(messages: List[Dict[str, Any]], tool_call_ids: List[str]) -> List[Dict[str, Any]]:
        """删除与指定工具调用ID相关的工具响应"""
        result = []
        for msg in messages:
            # 跳过角色为"tool"且tool_call_id在要删除的列表中的消息
            if msg.get("role") == "tool" and msg.get("tool_call_id") in tool_call_ids:
                continue
                
            # 处理包含tool_responses的消息
            if "tool_responses" in msg:
                msg = copy.deepcopy(msg)
                msg["tool_responses"] = [
                    tr for tr in msg["tool_responses"] 
                    if tr.get("tool_call_id") not in tool_call_ids
                ]
                # 如果tool_responses为空，删除该字段
                if not msg["tool_responses"]:
                    del msg["tool_responses"]
                    
            result.append(msg)
        return result
    
    @staticmethod
    def add_tool_call(messages: List[Dict[str, Any]], index: int, 
                      tool_call: Dict[str, Any]) -> List[Dict[str, Any]]:
        """向指定消息添加工具调用"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            message = new_messages[index]
            
            # 确保消息角色是assistant
            if message.get("role") != "assistant":
                message["role"] = "assistant"
                
            # 添加tool_calls字段
            if "tool_calls" not in message:
                message["tool_calls"] = []
                
            # 确保tool_call有id字段
            if "id" not in tool_call and "function" in tool_call:
                # 生成简单的ID
                import uuid
                tool_call["id"] = f"call_{uuid.uuid4().hex[:8]}"
                
            message["tool_calls"].append(tool_call)
            return new_messages
        raise IndexError(f"索引 {index} 超出消息列表范围 (0-{len(messages)-1})")
    
    @staticmethod
    def add_function_call(messages: List[Dict[str, Any]], index: int, 
                         function_call: Dict[str, Any]) -> List[Dict[str, Any]]:
        """向指定消息添加函数调用(旧版API)"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            message = new_messages[index]
            
            # 确保消息角色是assistant
            if message.get("role") != "assistant":
                message["role"] = "assistant"
                
            # 添加function_call字段
            message["function_call"] = function_call
            return new_messages
        raise IndexError(f"索引 {index} 超出消息列表范围 (0-{len(messages)-1})")
    
    @staticmethod
    def delete_tool_call(messages: List[Dict[str, Any]], tool_call_id: str) -> List[Dict[str, Any]]:
        """删除特定ID的工具调用及其相关的工具响应"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # 查找并处理包含该工具调用的消息
        for msg in new_messages:
            if "tool_calls" in msg:
                # 查找要删除的工具调用
                tool_calls = msg["tool_calls"]
                tool_call_index = next((i for i, tc in enumerate(tool_calls) 
                                        if tc.get("id") == tool_call_id), None)
                
                if tool_call_index is not None:
                    # 删除工具调用
                    del tool_calls[tool_call_index]
                    
                    # 如果tool_calls为空，删除该字段
                    if not tool_calls:
                        del msg["tool_calls"]
        
        # 删除相关的工具响应
        new_messages = MessageUtils._remove_related_tool_responses(new_messages, [tool_call_id])
        
        return new_messages
    
    @staticmethod
    def delete_function_call(messages: List[Dict[str, Any]], index: int) -> List[Dict[str, Any]]:
        """删除指定消息中的函数调用(旧版API)"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            message = new_messages[index]
            
            if "function_call" in message:
                # 记录函数名，用于查找和删除函数响应
                func_name = message["function_call"].get("name")
                del message["function_call"]
                
                # 删除相关的函数响应
                if func_name:
                    new_messages = [
                        msg for msg in new_messages 
                        if not (msg.get("role") == "function" and msg.get("name") == func_name)
                    ]
            
            return new_messages
        raise IndexError(f"索引 {index} 超出消息列表范围 (0-{len(messages)-1})")
    
    @staticmethod
    def add_tool_response(messages: List[Dict[str, Any]], 
                         tool_call_id: str, 
                         content: str) -> List[Dict[str, Any]]:
        """为指定的工具调用添加工具响应"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # 创建工具响应对象
        tool_response = {
            "tool_call_id": tool_call_id,
            "role": "tool",
            "content": content
        }
        
        # 查找工具调用所在的消息
        call_msg = None
        for msg in new_messages:
            for tc in msg.get("tool_calls", []):
                if tc.get("id") == tool_call_id:
                    call_msg = msg
                    break
            if call_msg:
                break
        
        if not call_msg:
            raise ValueError(f"未找到ID为 {tool_call_id} 的工具调用")
        
        # 寻找工具响应应该放置的位置，通常是在下一条消息中
        call_idx = new_messages.index(call_msg)
        
        # 选项1: 添加为独立的工具响应消息
        tool_msg = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        }
        
        # 插入到工具调用消息之后
        new_messages.insert(call_idx + 1, tool_msg)
        
        # 选项2: 也添加到可能存在的聚合响应消息中
        for msg in new_messages:
            if "tool_responses" in msg:
                # 移除可能存在的相同ID的响应
                msg["tool_responses"] = [
                    tr for tr in msg["tool_responses"] 
                    if tr.get("tool_call_id") != tool_call_id
                ]
                # 添加新响应
                msg["tool_responses"].append(tool_response)
        
        return new_messages
    
    @staticmethod
    def add_function_response(messages: List[Dict[str, Any]], 
                             function_name: str, 
                             content: str) -> List[Dict[str, Any]]:
        """为指定的函数调用添加函数响应(旧版API)"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # 查找函数调用所在的消息
        call_msg = None
        call_idx = -1
        for i, msg in enumerate(new_messages):
            if "function_call" in msg and msg["function_call"].get("name") == function_name:
                call_msg = msg
                call_idx = i
                break
        
        if not call_msg:
            raise ValueError(f"未找到名为 {function_name} 的函数调用")
        
        # 创建函数响应消息
        func_msg = {
            "role": "function",
            "name": function_name,
            "content": content
        }
        
        # 插入到函数调用消息之后
        new_messages.insert(call_idx + 1, func_msg)
        
        return new_messages
    
    @staticmethod
    def update_tool_call(messages: List[Dict[str, Any]], 
                        tool_call_id: str, 
                        updated_tool_call: Dict[str, Any]) -> List[Dict[str, Any]]:
        """更新特定ID的工具调用"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # 确保更新的工具调用保持相同的ID
        updated_tool_call["id"] = tool_call_id
        
        # 查找并更新工具调用
        for msg in new_messages:
            if "tool_calls" in msg:
                for i, tc in enumerate(msg["tool_calls"]):
                    if tc.get("id") == tool_call_id:
                        msg["tool_calls"][i] = updated_tool_call
                        return new_messages
        
        raise ValueError(f"未找到ID为 {tool_call_id} 的工具调用")
    
    @staticmethod
    def update_function_call(messages: List[Dict[str, Any]], 
                           index: int, 
                           updated_function_call: Dict[str, Any]) -> List[Dict[str, Any]]:
        """更新指定消息中的函数调用(旧版API)"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            message = new_messages[index]
            
            if "function_call" not in message:
                raise ValueError(f"索引 {index} 的消息不包含函数调用")
            
            # 记录旧的函数名
            old_func_name = message["function_call"].get("name")
            new_func_name = updated_function_call.get("name")
            
            # 更新函数调用
            message["function_call"] = updated_function_call
            
            # 如果函数名改变，更新相关的函数响应
            if old_func_name and new_func_name and old_func_name != new_func_name:
                for msg in new_messages:
                    if msg.get("role") == "function" and msg.get("name") == old_func_name:
                        msg["name"] = new_func_name
            
            return new_messages
        raise IndexError(f"索引 {index} 超出消息列表范围 (0-{len(messages)-1})")
    
    @staticmethod
    def update_tool_response(messages: List[Dict[str, Any]], 
                           tool_call_id: str, 
                           updated_content: str) -> List[Dict[str, Any]]:
        """更新特定ID的工具响应"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # 更新独立的工具响应消息
        for msg in new_messages:
            if msg.get("role") == "tool" and msg.get("tool_call_id") == tool_call_id:
                msg["content"] = updated_content
        
        # 更新聚合的工具响应
        for msg in new_messages:
            if "tool_responses" in msg:
                for tr in msg["tool_responses"]:
                    if tr.get("tool_call_id") == tool_call_id:
                        tr["content"] = updated_content
        
        return new_messages
    
    @staticmethod
    def update_function_response(messages: List[Dict[str, Any]],
                               function_name: str,
                               updated_content: str) -> List[Dict[str, Any]]:
        """更新特定函数名的函数响应(旧版API)"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # 更新函数响应消息
        for msg in new_messages:
            if msg.get("role") == "function" and msg.get("name") == function_name:
                msg["content"] = updated_content
        
        return new_messages
    
    @staticmethod
    def delete_tool_response(messages: List[Dict[str, Any]], 
                           tool_call_id: str) -> List[Dict[str, Any]]:
        """删除特定ID的工具响应"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # 删除独立的工具响应消息
        new_messages = [
            msg for msg in new_messages 
            if not (msg.get("role") == "tool" and msg.get("tool_call_id") == tool_call_id)
        ]
        
        # 从聚合响应中删除
        for msg in new_messages:
            if "tool_responses" in msg:
                msg["tool_responses"] = [
                    tr for tr in msg["tool_responses"] 
                    if tr.get("tool_call_id") != tool_call_id
                ]
                # 如果tool_responses为空，删除该字段
                if not msg["tool_responses"]:
                    del msg["tool_responses"]
        
        return new_messages
    
    @staticmethod
    def delete_function_response(messages: List[Dict[str, Any]], 
                              function_name: str) -> List[Dict[str, Any]]:
        """删除特定函数名的函数响应(旧版API)"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # 删除函数响应消息
        new_messages = [
            msg for msg in new_messages 
            if not (msg.get("role") == "function" and msg.get("name") == function_name)
        ]
        
        return new_messages
    
    @staticmethod
    def change_message_role(messages: List[Dict[str, Any]], 
                          index: int, 
                          new_role: str) -> List[Dict[str, Any]]:
        """修改指定消息的角色"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            message = new_messages[index]
            old_role = message.get("role")
            
            # 特殊情况处理
            if old_role == "assistant" and new_role != "assistant":
                # 如果消息从assistant变为其他角色，需要移除工具调用和函数调用
                if "tool_calls" in message:
                    tool_call_ids = [tc.get("id") for tc in message.get("tool_calls", [])]
                    # 移除工具调用
                    del message["tool_calls"]
                    # 移除相关的工具响应
                    new_messages = MessageUtils._remove_related_tool_responses(new_messages, tool_call_ids)
                
                if "function_call" in message:
                    # 移除函数调用
                    func_name = message["function_call"].get("name")
                    del message["function_call"]
                    # 移除相关的函数响应
                    if func_name:
                        new_messages = [
                            msg for msg in new_messages 
                            if not (msg.get("role") == "function" and msg.get("name") == func_name)
                        ]
            
            elif new_role == "assistant" and old_role != "assistant":
                # 如果消息变为assistant，不需要特殊处理，角色变更即可
                pass
            
            elif old_role == "function" and new_role != "function":
                # 如果消息从function变为其他角色，需要移除name字段
                if "name" in message:
                    del message["name"]
            
            elif old_role == "tool" and new_role != "tool":
                # 如果消息从tool变为其他角色，需要移除tool_call_id字段
                if "tool_call_id" in message:
                    tool_call_id = message["tool_call_id"]
                    del message["tool_call_id"]
                    
                    # 从聚合响应中删除
                    for msg in new_messages:
                        if "tool_responses" in msg:
                            msg["tool_responses"] = [
                                tr for tr in msg["tool_responses"] 
                                if tr.get("tool_call_id") != tool_call_id
                            ]
                            # 如果tool_responses为空，删除该字段
                            if not msg["tool_responses"]:
                                del msg["tool_responses"]
            
            # 更新角色
            message["role"] = new_role
            
            return new_messages
        raise IndexError(f"索引 {index} 超出消息列表范围 (0-{len(messages)-1})")
    
    @staticmethod
    def convert_function_call_to_tool_call(messages: List[Dict[str, Any]], 
                                         index: int) -> List[Dict[str, Any]]:
        """将旧版函数调用转换为新版工具调用"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            message = new_messages[index]
            
            if "function_call" not in message:
                raise ValueError(f"索引 {index} 的消息不包含函数调用")
            
            # 创建工具调用
            import uuid
            tool_call = {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": message["function_call"]
            }
            
            # 添加到工具调用列表
            if "tool_calls" not in message:
                message["tool_calls"] = []
            message["tool_calls"].append(tool_call)
            
            # 移除旧的函数调用
            del message["function_call"]
            
            # 查找相关的函数响应并转换为工具响应
            func_name = tool_call["function"].get("name")
            tool_call_id = tool_call["id"]
            
            if func_name:
                for i, msg in enumerate(new_messages):
                    if msg.get("role") == "function" and msg.get("name") == func_name:
                        # 转换为工具响应
                        tool_msg = {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": msg.get("content", "")
                        }
                        new_messages[i] = tool_msg
                        
                        # 也添加到聚合响应
                        message["tool_responses"] = message.get("tool_responses", [])
                        message["tool_responses"].append({
                            "tool_call_id": tool_call_id,
                            "role": "tool",
                            "content": msg.get("content", "")
                        })
            
            return new_messages
        raise IndexError(f"索引 {index} 超出消息列表范围 (0-{len(messages)-1})")
    
    @staticmethod
    def filter_messages(messages: List[Dict[str, Any]], 
                       filter_func: Callable[[Dict[str, Any]], bool]) -> List[Dict[str, Any]]:
        """使用自定义过滤函数筛选消息"""
        return [msg for msg in messages if filter_func(msg)]
    
    @staticmethod
    def search_messages(messages: List[Dict[str, Any]], 
                      search_text: str,
                      case_sensitive: bool = False) -> List[int]:
        """搜索消息内容，返回匹配的消息索引列表"""
        result = []
        pattern = re.compile(search_text, re.IGNORECASE if not case_sensitive else 0)
        
        for i, msg in enumerate(messages):
            content = msg.get("content", "")
            if content and isinstance(content, str) and pattern.search(content):
                result.append(i)
        
        return result
    
    @staticmethod
    def get_conversation_summary(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取对话摘要统计信息"""
        summary = {
            "total_messages": len(messages),
            "by_role": {},
            "tool_calls": 0,
            "function_calls": 0,
            "tool_responses": 0,
            "function_responses": 0
        }
        
        for msg in messages:
            # 统计角色
            role = msg.get("role", "unknown")
            summary["by_role"][role] = summary["by_role"].get(role, 0) + 1
            
            # 统计工具调用
            if "tool_calls" in msg:
                summary["tool_calls"] += len(msg["tool_calls"])
            
            # 统计函数调用
            if "function_call" in msg:
                summary["function_calls"] += 1
            
            # 统计工具响应
            if role == "tool":
                summary["tool_responses"] += 1
            
            # 统计聚合工具响应
            if "tool_responses" in msg:
                summary["tool_responses"] += len(msg["tool_responses"])
            
            # 统计函数响应
            if role == "function":
                summary["function_responses"] += 1
        
        return summary