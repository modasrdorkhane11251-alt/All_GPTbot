import base64, httpx
from .config import S
class ProviderError(Exception): pass
async def ask(provider,model,prompt,image=None,mime="image/jpeg"):
    if provider=="gemini":
        if not S.gemini_key: raise ProviderError("GEMINI_API_KEY is not configured.")
        parts=[{"text":prompt}]
        if image: parts.append({"inline_data":{"mime_type":mime,"data":base64.b64encode(image).decode()}})
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{model or S.gemini_model}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=S.timeout) as client:
                r=await client.post(url,params={"key":S.gemini_key},json={"contents":[{"role":"user","parts":parts}]})
                r.raise_for_status(); return "".join(x.get("text","") for x in r.json()["candidates"][0]["content"]["parts"])
        except (httpx.HTTPError,KeyError,IndexError,ValueError) as e: raise ProviderError(f"AI request failed ({type(e).__name__}).")
    if provider!="openai": raise ProviderError("Supported providers: openai, gemini.")
    if not S.openai_key: raise ProviderError("OPENAI_API_KEY is not configured.")
    content=prompt
    if image: content=[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:{mime};base64,{base64.b64encode(image).decode()}"}}]
    try:
        async with httpx.AsyncClient(timeout=S.timeout) as client:
            r=await client.post(S.openai_url+"/chat/completions",headers={"Authorization":"Bearer "+S.openai_key},json={"model":model or S.openai_model,"messages":[{"role":"user","content":content}]})
            r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError,KeyError,IndexError,ValueError) as e: raise ProviderError(f"AI request failed ({type(e).__name__}).")
