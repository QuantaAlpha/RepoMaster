from typing import List, Dict, Any, Optional, Union, Tuple, Callable
import copy
import re


class MessageUtils:
    """AutoGen message processing utility library
    
    Provides a series of methods for reading, adding, modifying, and deleting elements in AutoGen message lists.
    Specially handles complex situations such as tool calls, function calls, and role information.
    """
    
    @staticmethod
    def deep_copy_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create a deep copy of the message list to avoid modifying original data"""
        return copy.deepcopy(messages)
    
    @staticmethod
    def get_message_by_index(messages: List[Dict[str, Any]], index: int) -> Dict[str, Any]:
        """Get message by index"""
        if 0 <= index < len(messages):
            return messages[index]
        raise IndexError(f"Index {index} is out of message list range (0-{len(messages)-1})")
    
    @staticmethod
    def get_messages_by_role(messages: List[Dict[str, Any]], role: str) -> List[Dict[str, Any]]:
        """Get all messages with specified role"""
        return [msg for msg in messages if msg.get("role") == role]
    
    @staticmethod
    def get_messages_by_name(messages: List[Dict[str, Any]], name: str) -> List[Dict[str, Any]]:
        """Get all messages with specified name"""
        return [msg for msg in messages if msg.get("name") == name]
    
    @staticmethod
    def get_last_message(messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Get the last message"""
        return messages[-1] if messages else None
    
    @staticmethod
    def get_tool_calls(message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get tool calls list from message"""
        return message.get("tool_calls", [])
    
    @staticmethod
    def get_function_call(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get function call from message (legacy API)"""
        return message.get("function_call")
    
    @staticmethod
    def get_tool_responses(message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get tool responses list from message"""
        return message.get("tool_responses", [])
    
    @staticmethod
    def find_related_tool_response(messages: List[Dict[str, Any]], tool_call_id: str) -> Optional[Dict[str, Any]]:
        """Find tool response related to specific tool call ID"""
        for msg in messages:
            for response in msg.get("tool_responses", []):
                if response.get("tool_call_id") == tool_call_id:
                    return response
        return None
    
    @staticmethod
    def find_related_tool_call(messages: List[Dict[str, Any]], tool_call_id: str) -> Optional[Dict[str, Any]]:
        """Find tool call related to specific tool call ID"""
        for msg in messages:
            for tool_call in msg.get("tool_calls", []):
                if tool_call.get("id") == tool_call_id:
                    return tool_call
        return None
    
    @staticmethod
    def find_message_with_tool_call_id(messages: List[Dict[str, Any]], tool_call_id: str) -> Optional[Dict[str, Any]]:
        """Find message containing specific tool call ID"""
        for msg in messages:
            for tool_call in msg.get("tool_calls", []):
                if tool_call.get("id") == tool_call_id:
                    return msg
        return None
    
    @staticmethod
    def find_message_with_tool_response_id(messages: List[Dict[str, Any]], tool_call_id: str) -> Optional[Dict[str, Any]]:
        """Find message containing specific tool response ID"""
        for msg in messages:
            for response in msg.get("tool_responses", []):
                if response.get("tool_call_id") == tool_call_id:
                    return msg
        return None
    
    @staticmethod
    def add_message(messages: List[Dict[str, Any]], message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Add new message to message list"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        new_messages.append(message)
        return new_messages
    
    @staticmethod
    def update_message(messages: List[Dict[str, Any]], index: int, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Update message at specified index"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            new_messages[index] = message
            return new_messages
        raise IndexError(f"Index {index} is out of message list range (0-{len(messages)-1})")
    
    @staticmethod
    def delete_message(messages: List[Dict[str, Any]], index: int) -> List[Dict[str, Any]]:
        """Delete message at specified index"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            # Check if related tool responses need to be deleted
            message = new_messages[index]
            # If deleted message contains tool calls, need to delete related tool response messages
            if "tool_calls" in message:
                tool_call_ids = [tc.get("id") for tc in message.get("tool_calls", [])]
                new_messages = MessageUtils._remove_related_tool_responses(new_messages, tool_call_ids)
            
            # If deleted message is tool response, may need to remove tool_responses field from other messages
            if message.get("role") == "tool":
                tool_call_id = message.get("tool_call_id")
                if tool_call_id:
                    for msg in new_messages:
                        if "tool_responses" in msg:
                            msg["tool_responses"] = [
                                tr for tr in msg["tool_responses"] 
                                if tr.get("tool_call_id") != tool_call_id
                            ]
                            # If tool_responses is empty, remove the field
                            if not msg["tool_responses"]:
                                del msg["tool_responses"]
            
            # Delete message
            del new_messages[index]
            return new_messages
        raise IndexError(f"Index {index} is out of message list range (0-{len(messages)-1})")
    
    @staticmethod
    def _remove_related_tool_responses(messages: List[Dict[str, Any]], tool_call_ids: List[str]) -> List[Dict[str, Any]]:
        """Delete tool responses related to specified tool call IDs"""
        result = []
        for msg in messages:
            # Skip messages with role "tool" whose tool_call_id is in the deletion list
            if msg.get("role") == "tool" and msg.get("tool_call_id") in tool_call_ids:
                continue
                
            # Process messages that contain tool_responses
            if "tool_responses" in msg:
                msg = copy.deepcopy(msg)
                msg["tool_responses"] = [
                    tr for tr in msg["tool_responses"] 
                    if tr.get("tool_call_id") not in tool_call_ids
                ]
                # If tool_responses is empty, remove the field
                if not msg["tool_responses"]:
                    del msg["tool_responses"]
                    
            result.append(msg)
        return result
    
    @staticmethod
    def add_tool_call(messages: List[Dict[str, Any]], index: int, 
                      tool_call: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Add a tool call to the specified message"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            message = new_messages[index]
            
            # Ensure the message role is assistant
            if message.get("role") != "assistant":
                message["role"] = "assistant"
                
            # Add tool_calls field
            if "tool_calls" not in message:
                message["tool_calls"] = []
                
            # Ensure the tool_call has an id field
            if "id" not in tool_call and "function" in tool_call:
                # Generate a simple ID
                import uuid
                tool_call["id"] = f"call_{uuid.uuid4().hex[:8]}"
                
            message["tool_calls"].append(tool_call)
            return new_messages
        raise IndexError(f"Index {index} is out of message list range (0-{len(messages)-1})")
    
    @staticmethod
    def add_function_call(messages: List[Dict[str, Any]], index: int, 
                         function_call: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Add a function call to the specified message (legacy API)"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            message = new_messages[index]
            
            # Ensure the message role is assistant
            if message.get("role") != "assistant":
                message["role"] = "assistant"
                
            # Add function_call field
            message["function_call"] = function_call
            return new_messages
        raise IndexError(f"Index {index} is out of message list range (0-{len(messages)-1})")
    
    @staticmethod
    def delete_tool_call(messages: List[Dict[str, Any]], tool_call_id: str) -> List[Dict[str, Any]]:
        """Delete the tool call with the specified ID and its related tool responses"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # Find and process the message that contains this tool call
        for msg in new_messages:
            if "tool_calls" in msg:
                # Locate the tool call to delete
                tool_calls = msg["tool_calls"]
                tool_call_index = next((i for i, tc in enumerate(tool_calls) 
                                        if tc.get("id") == tool_call_id), None)
                
                if tool_call_index is not None:
                    # Delete the tool call
                    del tool_calls[tool_call_index]
                    
                    # If tool_calls is empty, remove the field
                    if not tool_calls:
                        del msg["tool_calls"]
        
        # Delete related tool responses
        new_messages = MessageUtils._remove_related_tool_responses(new_messages, [tool_call_id])
        
        return new_messages
    
    @staticmethod
    def delete_function_call(messages: List[Dict[str, Any]], index: int) -> List[Dict[str, Any]]:
        """Delete the function call in the specified message (legacy API)"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            message = new_messages[index]
            
            if "function_call" in message:
                # Record the function name to find and delete its response
                func_name = message["function_call"].get("name")
                del message["function_call"]
                
                # Delete the related function response
                if func_name:
                    new_messages = [
                        msg for msg in new_messages 
                        if not (msg.get("role") == "function" and msg.get("name") == func_name)
                    ]
            
            return new_messages
        raise IndexError(f"Index {index} is out of message list range (0-{len(messages)-1})")
    
    @staticmethod
    def add_tool_response(messages: List[Dict[str, Any]], 
                         tool_call_id: str, 
                         content: str) -> List[Dict[str, Any]]:
        """Add a tool response for the specified tool call"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # Create the tool response object
        tool_response = {
            "tool_call_id": tool_call_id,
            "role": "tool",
            "content": content
        }
        
        # Find the message that contains the tool call
        call_msg = None
        for msg in new_messages:
            for tc in msg.get("tool_calls", []):
                if tc.get("id") == tool_call_id:
                    call_msg = msg
                    break
            if call_msg:
                break
        
        if not call_msg:
            raise ValueError(f"Tool call with ID {tool_call_id} was not found")
        
        # Determine where to place the tool response, typically in the next message
        call_idx = new_messages.index(call_msg)
        
        # Option 1: add as a standalone tool response message
        tool_msg = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        }
        
        # Insert after the tool call message
        new_messages.insert(call_idx + 1, tool_msg)
        
        # Option 2: also add to any existing aggregated response message
        for msg in new_messages:
            if "tool_responses" in msg:
                # Remove any existing response with the same ID
                msg["tool_responses"] = [
                    tr for tr in msg["tool_responses"] 
                    if tr.get("tool_call_id") != tool_call_id
                ]
                # Add the new response
                msg["tool_responses"].append(tool_response)
        
        return new_messages
    
    @staticmethod
    def add_function_response(messages: List[Dict[str, Any]], 
                             function_name: str, 
                             content: str) -> List[Dict[str, Any]]:
        """Add a function response for the specified function call (legacy API)"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # Find the message that contains the function call
        call_msg = None
        call_idx = -1
        for i, msg in enumerate(new_messages):
            if "function_call" in msg and msg["function_call"].get("name") == function_name:
                call_msg = msg
                call_idx = i
                break
        
        if not call_msg:
            raise ValueError(f"Function call named {function_name} was not found")
        
        # Create the function response message
        func_msg = {
            "role": "function",
            "name": function_name,
            "content": content
        }
        
        # Insert after the function call message
        new_messages.insert(call_idx + 1, func_msg)
        
        return new_messages
    
    @staticmethod
    def update_tool_call(messages: List[Dict[str, Any]], 
                        tool_call_id: str, 
                        updated_tool_call: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Update the tool call with the specified ID"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # Ensure the updated tool call keeps the same ID
        updated_tool_call["id"] = tool_call_id
        
        # Find and update the tool call
        for msg in new_messages:
            if "tool_calls" in msg:
                for i, tc in enumerate(msg["tool_calls"]):
                    if tc.get("id") == tool_call_id:
                        msg["tool_calls"][i] = updated_tool_call
                        return new_messages
        
        raise ValueError(f"Tool call with ID {tool_call_id} was not found")
    
    @staticmethod
    def update_function_call(messages: List[Dict[str, Any]], 
                           index: int, 
                           updated_function_call: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Update the function call in the specified message (legacy API)"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            message = new_messages[index]
            
            if "function_call" not in message:
                raise ValueError(f"Message at index {index} does not contain a function call")
            
            # Record the old function name
            old_func_name = message["function_call"].get("name")
            new_func_name = updated_function_call.get("name")
            
            # Update the function call
            message["function_call"] = updated_function_call
            
            # If the function name changed, update related function responses
            if old_func_name and new_func_name and old_func_name != new_func_name:
                for msg in new_messages:
                    if msg.get("role") == "function" and msg.get("name") == old_func_name:
                        msg["name"] = new_func_name
            
            return new_messages
        raise IndexError(f"Index {index} is out of message list range (0-{len(messages)-1})")
    
    @staticmethod
    def update_tool_response(messages: List[Dict[str, Any]], 
                           tool_call_id: str, 
                           updated_content: str) -> List[Dict[str, Any]]:
        """Update the tool response with the specified ID"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # Update standalone tool response messages
        for msg in new_messages:
            if msg.get("role") == "tool" and msg.get("tool_call_id") == tool_call_id:
                msg["content"] = updated_content
        
        # Update aggregated tool responses
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
        """Update the function response for the specified function name (legacy API)"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # Update the function response message
        for msg in new_messages:
            if msg.get("role") == "function" and msg.get("name") == function_name:
                msg["content"] = updated_content
        
        return new_messages
    
    @staticmethod
    def delete_tool_response(messages: List[Dict[str, Any]], 
                           tool_call_id: str) -> List[Dict[str, Any]]:
        """Delete the tool response with the specified ID"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # Delete standalone tool response messages
        new_messages = [
            msg for msg in new_messages 
            if not (msg.get("role") == "tool" and msg.get("tool_call_id") == tool_call_id)
        ]
        
        # Remove from aggregated responses
        for msg in new_messages:
            if "tool_responses" in msg:
                msg["tool_responses"] = [
                    tr for tr in msg["tool_responses"] 
                    if tr.get("tool_call_id") != tool_call_id
                ]
                # If tool_responses is empty, remove the field
                if not msg["tool_responses"]:
                    del msg["tool_responses"]
        
        return new_messages
    
    @staticmethod
    def delete_function_response(messages: List[Dict[str, Any]], 
                              function_name: str) -> List[Dict[str, Any]]:
        """Delete the function response for the specified function name (legacy API)"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        
        # Delete function response messages
        new_messages = [
            msg for msg in new_messages 
            if not (msg.get("role") == "function" and msg.get("name") == function_name)
        ]
        
        return new_messages
    
    @staticmethod
    def change_message_role(messages: List[Dict[str, Any]], 
                          index: int, 
                          new_role: str) -> List[Dict[str, Any]]:
        """Change the role of the specified message"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            message = new_messages[index]
            old_role = message.get("role")
            
            # Special case handling
            if old_role == "assistant" and new_role != "assistant":
                # If the message changes from assistant to another role, remove tool and function calls
                if "tool_calls" in message:
                    tool_call_ids = [tc.get("id") for tc in message.get("tool_calls", [])]
                    # Remove tool calls
                    del message["tool_calls"]
                    # Remove related tool responses
                    new_messages = MessageUtils._remove_related_tool_responses(new_messages, tool_call_ids)
                
                if "function_call" in message:
                    # Remove the function call
                    func_name = message["function_call"].get("name")
                    del message["function_call"]
                    # Remove related function responses
                    if func_name:
                        new_messages = [
                            msg for msg in new_messages 
                            if not (msg.get("role") == "function" and msg.get("name") == func_name)
                        ]
            
            elif new_role == "assistant" and old_role != "assistant":
                # If the message becomes assistant, no special handling is required
                pass
            
            elif old_role == "function" and new_role != "function":
                # If the message changes from function to another role, remove the name field
                if "name" in message:
                    del message["name"]
            
            elif old_role == "tool" and new_role != "tool":
                # If the message changes from tool to another role, remove the tool_call_id field
                if "tool_call_id" in message:
                    tool_call_id = message["tool_call_id"]
                    del message["tool_call_id"]
                    
                    # Remove from aggregated responses
                    for msg in new_messages:
                        if "tool_responses" in msg:
                            msg["tool_responses"] = [
                                tr for tr in msg["tool_responses"] 
                                if tr.get("tool_call_id") != tool_call_id
                            ]
                            # If tool_responses is empty, remove the field
                            if not msg["tool_responses"]:
                                del msg["tool_responses"]
            
            # Update role
            message["role"] = new_role
            
            return new_messages
        raise IndexError(f"Index {index} is out of message list range (0-{len(messages)-1})")
    
    @staticmethod
    def convert_function_call_to_tool_call(messages: List[Dict[str, Any]], 
                                         index: int) -> List[Dict[str, Any]]:
        """Convert a legacy function call to a modern tool call"""
        new_messages = MessageUtils.deep_copy_messages(messages)
        if 0 <= index < len(new_messages):
            message = new_messages[index]
            
            if "function_call" not in message:
                raise ValueError(f"Message at index {index} does not contain a function call")
            
            # Create the tool call
            import uuid
            tool_call = {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": message["function_call"]
            }
            
            # Add to the tool_calls list
            if "tool_calls" not in message:
                message["tool_calls"] = []
            message["tool_calls"].append(tool_call)
            
            # Remove the old function call
            del message["function_call"]
            
            # Find the related function response and convert it to a tool response
            func_name = tool_call["function"].get("name")
            tool_call_id = tool_call["id"]
            
            if func_name:
                for i, msg in enumerate(new_messages):
                    if msg.get("role") == "function" and msg.get("name") == func_name:
                        # Convert to a tool response
                        tool_msg = {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": msg.get("content", "")
                        }
                        new_messages[i] = tool_msg
                        
                        # Also add to aggregated responses
                        message["tool_responses"] = message.get("tool_responses", [])
                        message["tool_responses"].append({
                            "tool_call_id": tool_call_id,
                            "role": "tool",
                            "content": msg.get("content", "")
                        })
            
            return new_messages
        raise IndexError(f"Index {index} is out of message list range (0-{len(messages)-1})")
    
    @staticmethod
    def filter_messages(messages: List[Dict[str, Any]], 
                       filter_func: Callable[[Dict[str, Any]], bool]) -> List[Dict[str, Any]]:
        """Filter messages using a custom filter function"""
        return [msg for msg in messages if filter_func(msg)]
    
    @staticmethod
    def search_messages(messages: List[Dict[str, Any]], 
                      search_text: str,
                      case_sensitive: bool = False) -> List[int]:
        """Search message content and return a list of matching message indices"""
        result = []
        pattern = re.compile(search_text, re.IGNORECASE if not case_sensitive else 0)
        
        for i, msg in enumerate(messages):
            content = msg.get("content", "")
            if content and isinstance(content, str) and pattern.search(content):
                result.append(i)
        
        return result
    
    @staticmethod
    def get_conversation_summary(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get conversation summary statistics"""
        summary = {
            "total_messages": len(messages),
            "by_role": {},
            "tool_calls": 0,
            "function_calls": 0,
            "tool_responses": 0,
            "function_responses": 0
        }
        
        for msg in messages:
            # Count roles
            role = msg.get("role", "unknown")
            summary["by_role"][role] = summary["by_role"].get(role, 0) + 1
            
            # Count tool calls
            if "tool_calls" in msg:
                summary["tool_calls"] += len(msg["tool_calls"])
            
            # Count function calls
            if "function_call" in msg:
                summary["function_calls"] += 1
            
            # Count tool responses
            if role == "tool":
                summary["tool_responses"] += 1
            
            # Count aggregated tool responses
            if "tool_responses" in msg:
                summary["tool_responses"] += len(msg["tool_responses"])
            
            # Count function responses
            if role == "function":
                summary["function_responses"] += 1
        
        return summary