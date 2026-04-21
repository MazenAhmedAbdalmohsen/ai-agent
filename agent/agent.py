"""
AI Agent Core — Autonomous Agent with full PC control
"""

import json
from typing import Optional
from config import settings
from agent.memory import ConversationMemory
from agent.tools import TOOLS, execute_tool


class AIAgent:
    """
    An autonomous AI Agent that can control PC like a human.
    Can chain multiple actions, make decisions, and complete complex tasks.
    """

    def __init__(self, memory: Optional[ConversationMemory] = None):
        from groq import Groq
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = settings.MODEL
        self.fallback_model = settings.FALLBACK_MODEL
        self.memory = memory or ConversationMemory()
        self.system_prompt = settings.SYSTEM_PROMPT
        self._using_fallback = False  # Track if we switched to fallback

    async def run(self, user_message: str) -> tuple[str, list[dict]]:
        """
        Process user message through the agent loop.
        For PC control: may execute multiple chained actions.
        """
        self.memory.add_message("user", user_message)

        messages = self._prepare_messages()
        all_tool_calls = []

        # Agent loop - allow multiple tool calls for complex tasks
        max_iterations = 10
        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1

                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        max_tokens=settings.MAX_TOKENS,
                        messages=messages,
                        tools=self._convert_tools_to_groq_format(),
                        tool_choice="auto",
                    )

                    message = response.choices[0].message

                    # Check if model wants to use tools
                    if message.tool_calls:
                        # Add assistant message with tool calls
                        messages.append({
                            "role": "assistant",
                            "content": message.content or "",
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments
                                    }
                                } for tc in message.tool_calls
                            ]
                        })

                        # Execute all tool calls
                        for tool_call in message.tool_calls:
                            tool_name = tool_call.function.name

                            try:
                                tool_input = json.loads(tool_call.function.arguments)
                            except Exception:
                                tool_input = {}

                            # Execute the tool
                            result = execute_tool(tool_name, tool_input)

                            all_tool_calls.append({
                                "tool": tool_name,
                                "input": tool_input,
                                "result": result
                            })

                            # Add tool result to conversation
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": str(result)
                            })

                            # Special handling for PC control - continue loop for chained actions
                            if tool_name == "pc_control" and iteration < max_iterations:
                                continue

                    else:
                        # No more tool calls - final response
                        reply = message.content or "I couldn't generate a response."
                        
                        # Add fallback notice if we switched models
                        if self._using_fallback:
                            reply = f"⚠️ Using fallback model ({self.fallback_model}) due to rate limit on primary model.\n\n{reply}"
                        
                        self.memory.add_message("assistant", reply)
                        return reply, all_tool_calls

                except Exception as e:
                    error_str = str(e)

                    # Handle rate limit — auto-switch to fallback model
                    if "rate_limit_exceeded" in error_str or "Rate limit reached" in error_str:
                        if not self._using_fallback and self.fallback_model != self.model:
                            self._using_fallback = True
                            self.model = self.fallback_model
                            print(f"⚠️ Rate limit hit on primary model. Switching to fallback: {self.fallback_model}")
                            # Retry the same iteration with new model
                            continue
                        else:
                            # Already on fallback or no fallback configured
                            error_msg = (
                                f"⏳ Rate limit reached for all available models.\n"
                                f"Primary: {settings.MODEL}\n"
                                f"Fallback: {settings.FALLBACK_MODEL}\n\n"
                                f"Details: {error_str}"
                            )
                            self.memory.add_message("assistant", error_msg)
                            return error_msg, all_tool_calls

                    # Handle tool_use_failed / failed_generation: instruct model to retry
                    if "tool_use_failed" in error_str or "failed_generation" in error_str:
                        messages.append({
                            "role": "user",
                            "content": (
                                "Your last response contained text instead of a tool call. "
                                "You MUST call the appropriate tool immediately without any preamble or explanation."
                            )
                        })
                        continue

                    # For all other errors, surface them
                    error_msg = f"Error: {error_str}"
                    self.memory.add_message("assistant", error_msg)
                    return error_msg, all_tool_calls

        except Exception as outer_e:
            error_msg = f"Agent loop error: {str(outer_e)}"
            self.memory.add_message("assistant", error_msg)
            return error_msg, all_tool_calls

        # Max iterations reached
        final_msg = "I completed the task with multiple steps."
        self.memory.add_message("assistant", final_msg)
        return final_msg, all_tool_calls

    def _prepare_messages(self) -> list:
        """Prepare messages with limited history to stay under token limits."""
        messages = [{"role": "system", "content": self.system_prompt}]

        # Get last 12 messages (6 exchanges) for better context
        recent_messages = self.memory.get_messages()[-12:]
        messages.extend(recent_messages)

        return messages

    def _convert_tools_to_groq_format(self) -> list:
        """Convert tools to Groq/OpenAI tool format."""
        groq_tools = []
        for tool in TOOLS:
            groq_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"]
                }
            })
        return groq_tools