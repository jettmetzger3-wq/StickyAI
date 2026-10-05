// node --test test/  (bundles the function with an in-memory Blobs store, no Netlify account needed)
import { test } from "node:test";
import assert from "node:assert/strict";
import { build } from "esbuild";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";

const here = dirname(fileURLToPath(import.meta.url));
const out = join(tmpdir(), `studio-link-${process.pid}.mjs`);
await build({ entryPoints: [join(here, "../netlify/functions/studio-link.mts")], bundle: true, platform: "node",
              format: "esm", outfile: out, alias: { "@netlify/blobs": join(here, "fake-blobs.mjs") }, logLevel: "error" });
const SECRET = "s3cret-s3cret-s3cret";
globalThis.Netlify = { env: { get: (k) => (k === "STUDIO_LINK_SECRET" ? SECRET : undefined) },
                       context: { deploy: { context: "production" } } };
const { default: handler } = await import(out);
const post = (body, secret = SECRET) => handler(new Request("https://x/api/studio-link", {
  method: "POST", headers: { authorization: `Bearer ${secret}`, "content-type": "application/json" },
  body: JSON.stringify(body) }), {});
const get = async () => (await handler(new Request("https://x/api/studio-link"), {})).json();

test("offline until the studio reports a link", async () => {
  assert.deepEqual(await get(), { online: false });
});

test("wrong secret and foreign links are refused", async () => {
  assert.equal((await post({ url: "https://abc.trycloudflare.com" }, "nope")).status, 401);
  assert.equal((await post({ url: "https://evil.example.com" })).status, 400);
  assert.equal((await post({ url: "https://abc.trycloudflare.com/../x" })).status, 400);
});

test("the studio link is shared, then goes offline", async () => {
  assert.equal((await post({ url: "https://lucky-words.trycloudflare.com" })).status, 200);
  assert.deepEqual(await get(), { online: true, url: "https://lucky-words.trycloudflare.com" });
  assert.equal((await post({ offline: true })).status, 200);
  assert.deepEqual(await get(), { online: false });
});
