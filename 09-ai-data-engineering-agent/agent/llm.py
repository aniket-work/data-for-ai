"""The agent loop: model -> tool calls -> results -> model, until it calls its finish tool.

Works with any OpenAI-compatible chat endpoint that supports tool calling.
"""
import json, re, time
from openai import OpenAI
from . import config, trace

def client():
    c = OpenAI(base_url=config.BASE_URL, api_key=config.API_KEY)
    model = config.MODEL or c.models.list().data[0].id
    return c, model

def tool_schema(name, description, props, required=None):
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": props, "required": required if required is not None else list(props)}}}

REASON = {"type": "string", "description": "one short sentence: why you are calling this tool"}

def split_thinking(msg):
    """Reasoning models (Qwen3, DeepSeek-R1 ...) return their thinking separately or inside <think> tags."""
    think = getattr(msg, "reasoning_content", None) or ""
    content = msg.content or ""
    m = re.search(r"<think>(.*?)</think>", content, re.S)
    if m:
        think, content = m.group(1), content.replace(m.group(0), "")
    think = " ".join(think.split())
    return (think[:220] + " ..." if len(think) > 220 else think) or None, content.strip()

def run(system, user, tools, finish="finish", max_steps=None):
    """tools: {name: (schema, fn)}. Returns the arguments the model passed to the finish tool."""
    c, model = client()
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    schemas = [s for s, _ in tools.values()]
    for step in range(1, (max_steps or config.MAX_STEPS) + 1):
        t0 = time.time()
        with trace.console.status(f"[#64748B]step {step}: the model is thinking ...[/]", spinner="dots"):
            r = c.chat.completions.create(model=model, messages=msgs, tools=schemas, temperature=config.TEMPERATURE)
        msg = r.choices[0].message
        think, content = split_thinking(msg)
        trace.model_turn(step, time.time() - t0, r.usage.completion_tokens if r.usage else 0, think)
        calls = msg.tool_calls or []
        if not calls:
            if content:
                trace.final("final answer", content)
                return {"summary": content}
            msgs.append({"role": "user", "content": "Please use one of the tools."}); continue
        msgs.append({"role": "assistant", "content": content or None, "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in calls]})
        done = None
        for tc in calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            trace.tool_call(name, args)
            if name not in tools:
                out, ok = f"unknown tool {name}", False
            else:
                try:
                    out, ok = tools[name][1](**{k: v for k, v in args.items() if k != "reason"}), True
                except Exception as ex:                       # errors go back to the model so it can correct itself
                    out, ok = f"{type(ex).__name__}: {ex}", False
            if name != finish or not ok:
                trace.tool_result(out, ok)
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": str(out)})
            if name == finish and ok:
                done = args
        if done is not None:
            return done
    trace.final("stopped", f"no finish after {max_steps or config.MAX_STEPS} steps")
    return {}
