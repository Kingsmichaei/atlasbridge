// Code samples shown on the landing page, in the docs and in the playground.
// The base URL is the site's own origin, so samples are copy-paste ready on any deployment.

export const origin = () => window.location.origin;
export const baseUrl = () => `${origin()}/v1`;
export const SDK_INSTALL = 'pip install "git+https://github.com/Kingsmichaei/atlasbridge#subdirectory=sdk"';

export function openaiPython(key = "ab_YOUR_KEY") {
  return `from openai import OpenAI

client = OpenAI(
    api_key="${key}",
    base_url="${baseUrl()}",
)

reply = client.chat.completions.create(
    model="n-atlas",
    messages=[{"role": "user", "content": "Menene amfanin ruwa ga jikin dan Adam?"}],
)
print(reply.choices[0].message.content)   # answers in Hausa`;
}

export function curl(key = "ab_YOUR_KEY") {
  return `curl ${baseUrl()}/chat/completions \\
  -H "Authorization: Bearer ${key}" \\
  -H "Content-Type: application/json" \\
  -d '{"model": "n-atlas", "messages": [{"role": "user", "content": "Sannu"}]}'`;
}

export function jsFetch(key = "ab_YOUR_KEY") {
  return `const r = await fetch("${baseUrl()}/chat/completions", {
  method: "POST",
  headers: { "Content-Type": "application/json", Authorization: "Bearer ${key}" },
  body: JSON.stringify({
    model: "n-atlas",
    messages: [{ role: "user", content: "Bawo ni?" }],
  }),
});
const data = await r.json();
console.log(data.choices[0].message.content);`;
}

export function sdkPython(key = "ab_YOUR_KEY") {
  return `# ${SDK_INSTALL}
from atlasbridge import AtlasBridge

ab = AtlasBridge(api_key="${key}", base_url="${origin()}")
print(ab.chat("Kedu ka ị mere?"))                       # replies in Igbo
print(ab.chat("Tell me about Kano", language="hausa"))  # force the reply language
print(ab.translate("Good morning", to="yoruba"))
print(ab.detect_language("Kini anfaani omi fun ara eniyan?"))
for piece in ab.stream("Tell me about Lagos"):
    print(piece, end="")`;
}

export const quickSamples = (key?: string) => [
  { label: "Python (OpenAI SDK)", title: "app.py", code: openaiPython(key) },
  { label: "curl", title: "terminal", code: curl(key) },
  { label: "JavaScript", title: "app.js", code: jsFetch(key) },
  { label: "AtlasBridge SDK", title: "app.py", code: sdkPython(key) },
];
